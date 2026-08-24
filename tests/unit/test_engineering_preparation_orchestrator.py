import tempfile
import subprocess
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fam_os.adapters.filesystem import (
    BoundedFilesystemRepositoryObserver, CandidateWorkspaceAdapter,
)
from fam_os.adapters.sqlite import SQLiteEngineeringLoopStore
from fam_os.core.engineering import (
    CheckpointPolicy,
    EngineeringAuthority,
    EngineeringLoopBudget,
    EngineeringLoopStage,
    EngineeringOperation,
    EngineeringPreparationOrchestrator,
    EngineeringTaskDefinition,
    EngineeringTaskEnvelope,
    MasterEngineeringLoop,
    engineering_task_digest,
)
from fam_os.core.engineering.lifecycle_driver import EngineeringLifecycleDriver
from fam_os.core.engineering.repository import BoundedRepositoryPlanner, RepositoryAnalysisRequest
from fam_os.core.engineering.git_delivery import GitRepositoryObservation


NOW = datetime(2026, 7, 19, 23, 30, tzinfo=timezone.utc)


class EngineeringPreparationOrchestratorTests(unittest.TestCase):
    def test_plain_folder_and_empty_git_directory_are_observed_without_git(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            (root / ".git").mkdir()
            (root / "README.md").write_text("plain workspace\n")

            evidence = BoundedFilesystemRepositoryObserver(clock=lambda: NOW).observe(
                "task-plain", str(root),
            )

            self.assertEqual(str(root), evidence.workspace_root)
            self.assertEqual("unversioned", evidence.git_state.head_revision)
            self.assertEqual(("README.md",), tuple(item.path for item in evidence.files))

    def test_nested_workspace_is_normalized_to_repository_top_level(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            subprocess.run(("git", "init", "-q", "-b", "main", str(root)), check=True)
            nested = root / "src/package"
            nested.mkdir(parents=True)
            (root / "README.md").write_text("repository root\n")

            evidence = BoundedFilesystemRepositoryObserver(clock=lambda: NOW).observe(
                "task-nested", str(nested),
            )

            self.assertEqual(str(root), evidence.workspace_root)
            self.assertIn("README.md", tuple(item.path for item in evidence.files))

    def test_real_bounded_observation_planning_and_candidate_creation_advance_loop(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            owner = root / "owner"
            owner.mkdir()
            (owner / "src").mkdir()
            (owner / "src/service.py").write_text("def service():\n    return 1\n")
            (owner / "tests").mkdir()
            (owner / "tests/test_service.py").write_text("def test_service():\n    assert True\n")
            (owner / "AGENTS.md").write_text("Keep Core separate from adapters.\n")
            definition = _definition(owner)
            store = SQLiteEngineeringLoopStore(root / "loop.sqlite3")
            loop = MasterEngineeringLoop(store)
            loop.start_defined(
                definition, EngineeringLoopBudget(100, 100, 10, 100, 100, 10000),
                instant=NOW,
            )
            observer = BoundedFilesystemRepositoryObserver(
                git=_Git(), clock=lambda: NOW,
            )
            orchestrator = EngineeringPreparationOrchestrator(
                observer, BoundedRepositoryPlanner(),
                CandidateWorkspaceAdapter(owner, root / "transactions"),
                EngineeringLifecycleDriver(loop, lambda *_args: None),
                _MemoryRecords(),
            )
            result = orchestrator.prepare(
                definition,
                RepositoryAnalysisRequest(
                    "analysis-1", definition.task.task_id,
                    definition.task.intent, (), 20, 20, 20,
                ),
            )
            self.assertEqual(EngineeringLoopStage.CANDIDATE_READY, loop.state(definition.task.task_id).stage)
            self.assertIn("src/service.py", result.analysis.relevant_paths)
            self.assertFalse(result.evidence.mutation_performed)
            self.assertTrue(Path(result.candidate.candidate_workspace).is_dir())
            store.close()

    def test_repository_symbolic_link_is_rejected_before_observation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "target").write_text("secret")
            (root / "link").symlink_to(root / "target")
            with self.assertRaises(PermissionError):
                BoundedFilesystemRepositoryObserver(git=_Git()).observe("task-1", str(root))

    def test_generated_dependency_links_are_pruned_without_following_them(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            owner = root / "owner"
            owner.mkdir()
            (owner / "package.json").write_text('{"name":"safe"}\n')
            (owner / "src").mkdir()
            (owner / "src/app.ts").write_text("export const safe = true;\n")
            (owner / "node_modules/.bin").mkdir(parents=True)
            (owner / "node_modules/tool.js").write_text("console.log('tool')\n")
            (owner / "node_modules/.bin/tool").symlink_to("../tool.js")
            (owner / ".next").mkdir()
            (owner / ".next/cache-link").symlink_to("/tmp")

            evidence = BoundedFilesystemRepositoryObserver(
                git=_Git(), clock=lambda: NOW,
            ).observe("task-1", str(owner.resolve()))
            candidate = CandidateWorkspaceAdapter(
                owner.resolve(), root / "transactions",
            ).create("task-1", now=NOW)

            observed = tuple(item.path for item in evidence.files)
            copied = tuple(item.path for item in candidate.entries)
            self.assertEqual(("package.json", "src/app.ts"), observed)
            self.assertEqual(("package.json", "src", "src/app.ts"), copied)
            self.assertFalse(
                (Path(candidate.candidate_workspace) / "node_modules").exists()
            )

    def test_candidate_snapshot_excludes_git_metadata(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            owner = root / "owner"
            owner.mkdir()
            (owner / ".git").mkdir()
            (owner / ".git/config").write_text("credential = secret")
            (owner / "source.py").write_text("value = 1\n")
            candidate = CandidateWorkspaceAdapter(
                owner, root / "transactions",
            ).create("task-1", now=NOW)
            self.assertEqual(("source.py",), tuple(item.path for item in candidate.entries))

    def test_candidate_failure_leaves_preparation_state_unadvanced(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            owner = root / "owner"
            owner.mkdir()
            (owner / "service.py").write_text("value = 1\n")
            definition = _definition(owner)
            store = SQLiteEngineeringLoopStore(root / "loop.sqlite3")
            loop = MasterEngineeringLoop(store)
            loop.start_defined(
                definition, EngineeringLoopBudget(10, 10, 10, 10, 10, 10),
                instant=NOW,
            )
            orchestrator = EngineeringPreparationOrchestrator(
                BoundedFilesystemRepositoryObserver(git=_Git(), clock=lambda: NOW),
                BoundedRepositoryPlanner(), _FailingCandidates(),
                EngineeringLifecycleDriver(loop, lambda *_args: None),
                _MemoryRecords(),
            )
            with self.assertRaises(RuntimeError):
                orchestrator.prepare(
                    definition, RepositoryAnalysisRequest(
                        "analysis-1", "task-1", definition.task.intent,
                        (), 10, 10, 10,
                    ),
                )
            self.assertEqual(EngineeringLoopStage.REQUESTED, loop.state("task-1").stage)
            store.close()

    def test_pending_record_is_reused_after_lifecycle_write_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            owner = root / "owner"
            owner.mkdir()
            (owner / "service.py").write_text("value = 1\n")
            definition, store, loop = _started(root, owner)
            records = _MemoryRecords()
            lifecycle = _FailOnceLifecycle(
                EngineeringLifecycleDriver(loop, lambda *_args: None),
            )
            orchestrator = _orchestrator(owner, root, lifecycle, records)
            request = _request(definition)
            with self.assertRaises(RuntimeError):
                orchestrator.prepare(definition, request)
            pending_id = records.value.candidate.candidate_id
            result = orchestrator.prepare(definition, request)
            self.assertEqual(pending_id, result.candidate.candidate_id)
            self.assertTrue(records.committed)
            self.assertEqual(EngineeringLoopStage.CANDIDATE_READY, loop.state("task-1").stage)
            store.close()

    def test_pending_record_reconciles_after_commit_marker_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            owner = root / "owner"
            owner.mkdir()
            (owner / "service.py").write_text("value = 1\n")
            definition, store, loop = _started(root, owner)
            records = _FailOnceCommitRecords()
            lifecycle = EngineeringLifecycleDriver(loop, lambda *_args: None)
            orchestrator = _orchestrator(owner, root, lifecycle, records)
            request = _request(definition)
            with self.assertRaises(RuntimeError):
                orchestrator.prepare(definition, request)
            revision = loop.state("task-1").revision
            result = orchestrator.prepare(definition, request)
            self.assertEqual(records.value.candidate.candidate_id, result.candidate.candidate_id)
            self.assertEqual(revision, loop.state("task-1").revision)
            self.assertTrue(records.committed)
            store.close()


def _definition(owner):
    task = EngineeringTaskEnvelope(
        "task-1", "owner-1", "grant-1",
        "Change the service and its tests", NOW, NOW + timedelta(hours=1),
        (str(owner),),
        (EngineeringAuthority.OBSERVE, EngineeringAuthority.PROPOSE,
         EngineeringAuthority.MODIFY, EngineeringAuthority.EXECUTE),
        (EngineeringOperation.READ, EngineeringOperation.REPLACE,
         EngineeringOperation.RUN_TOOL),
        ("src/**", "tests/**"), (".git/**",), ("python3",), (), (),
        100, 10, 10, 10000, None, None, CheckpointPolicy.EVERY_CHANGESET,
    )
    return EngineeringTaskDefinition(
        "definition-task-1", task, "acceptance-tests-1", NOW,
        engineering_task_digest(task),
    )


class _Git:
    def observe(self, task_id, root):
        return GitRepositoryObservation(
            "git-observation-1", task_id, str(root), "main", "1" * 40,
            (), ("refs/heads/main",), ("origin",), ("1" * 40,),
            "a" * 64, NOW,
        )


class _FailingCandidates:
    def create(self, task_id):
        raise RuntimeError("candidate storage unavailable")


class _MemoryRecords:
    def __init__(self):
        self.value = None
        self.committed = False

    def put(self, result):
        self.value = result
        self.committed = False

    def load(self, task_id):
        return self.value if self.value and self.value.candidate.task_id == task_id else None

    def load_pending(self, task_id):
        value = self.load(task_id)
        return value if value is not None and not self.committed else None

    def mark_committed(self, task_id, definition_id):
        if self.value is None or self.value.definition_id != definition_id:
            raise RuntimeError("preparation unavailable")
        self.committed = True


class _FailOnceCommitRecords(_MemoryRecords):
    def __init__(self):
        super().__init__()
        self.failed = False

    def mark_committed(self, task_id, definition_id):
        if not self.failed:
            self.failed = True
            raise RuntimeError("commit marker unavailable")
        super().mark_committed(task_id, definition_id)


class _FailOnceLifecycle:
    def __init__(self, lifecycle):
        self.lifecycle = lifecycle
        self.failed = False

    def preparation_is_recorded(self, *values):
        return self.lifecycle.preparation_is_recorded(*values)

    def record_preparation(self, *values):
        if not self.failed:
            self.failed = True
            raise RuntimeError("state store unavailable")
        return self.lifecycle.record_preparation(*values)


def _started(root, owner):
    definition = _definition(owner)
    store = SQLiteEngineeringLoopStore(root / "loop.sqlite3")
    loop = MasterEngineeringLoop(store)
    loop.start_defined(
        definition, EngineeringLoopBudget(10, 10, 10, 10, 10, 10), instant=NOW,
    )
    return definition, store, loop


def _orchestrator(owner, root, lifecycle, records):
    return EngineeringPreparationOrchestrator(
        BoundedFilesystemRepositoryObserver(git=_Git(), clock=lambda: NOW),
        BoundedRepositoryPlanner(),
        CandidateWorkspaceAdapter(owner, root / "transactions"),
        lifecycle, records,
    )


def _request(definition):
    return RepositoryAnalysisRequest(
        "analysis-1", "task-1", definition.task.intent, (), 10, 10, 10,
    )


if __name__ == "__main__":
    unittest.main()
