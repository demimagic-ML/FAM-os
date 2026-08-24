import hashlib
import subprocess
import tempfile
import unittest
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

from fam_os.adapters.git import LocalGitAdapter
from fam_os.adapters.sqlite import SQLitePublicationConsumptionStore
from fam_os.core.engineering import (
    GitLocalAction,
    GitLocalActionKind,
    GitPublicationKind,
    GitPublicationReceipt,
    GitPublicationService,
)
from fam_os.core.engineering.delegation import EngineeringDelegationMode
from tests.contract.schema_engineering_fixtures import NOW, engineering_grant_schema_values
from tests.contract.schema_git_fixtures import git_schema_values


class _Consumptions:
    def __init__(self):
        self.used = set()

    def consume_once(self, identity):
        if identity in self.used:
            return False
        self.used.add(identity)
        return True


class _Provider:
    def __init__(self):
        self.calls = []

    def publish(self, approval):
        self.calls.append(approval)
        return GitPublicationReceipt(
            "receipt-1", approval.approval_id, "test-provider",
            approval.remote_name, approval.target_ref,
            approval.expected_old_object_id, approval.proposed_new_object_id,
            "https://git.example/draft/1", True, NOW,
            hashlib.sha256(b"provider evidence").hexdigest(),
        )


class GitDeliveryTests(unittest.TestCase):
    def test_local_branch_exact_stage_commit_observe_blame_and_restore(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            subprocess.run(("git", "init", "-q", "-b", "main", str(root)), check=True)
            (root / "tracked.txt").write_text("first\n")
            subprocess.run(("git", "-C", str(root), "-c", "user.name=Fixture", "-c", "user.email=f@x", "add", "tracked.txt"), check=True)
            subprocess.run(("git", "-C", str(root), "-c", "user.name=Fixture", "-c", "user.email=f@x", "commit", "-qm", "initial"), check=True)
            adapter = LocalGitAdapter(clock=lambda: NOW)
            first = adapter.observe("task-1", root)
            branch = GitLocalAction(
                "branch-1", "task-1", str(root), GitLocalActionKind.CREATE_BRANCH,
                "feature/verified", (), None, "change-1", ("verify-1",),
                first.head_object_id, NOW,
            )
            adapter.apply(branch)
            (root / "tracked.txt").write_text("second\n")
            stage = GitLocalAction(
                "stage-1", "task-1", str(root), GitLocalActionKind.STAGE_PATHS,
                None, ("tracked.txt",), None, "change-1", ("verify-1",),
                first.head_object_id, NOW,
            )
            staged = adapter.apply(stage)
            self.assertEqual(("tracked.txt",), staged.staged_paths)
            commit = GitLocalAction(
                "commit-1", "task-1", str(root), GitLocalActionKind.COMMIT,
                None, (), "verified change", "change-1", ("verify-1",),
                first.head_object_id, NOW,
            )
            committed = adapter.apply(commit)
            self.assertNotEqual(committed.before_object_id, committed.after_object_id)
            self.assertIn("author ", adapter.blame(root, "tracked.txt"))
            self.assertEqual("feature/verified", adapter.observe("task-1", root).head_ref)

    def test_directory_inside_repository_resolves_to_canonical_top_level(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            subprocess.run(("git", "init", "-q", "-b", "main", str(root)), check=True)
            selected = root / "src/fam_os"
            selected.mkdir(parents=True)

            adapter = LocalGitAdapter(clock=lambda: NOW)
            observation = adapter.observe("task-nested", selected)

            self.assertEqual(root, adapter.repository_root(selected))
            self.assertEqual(str(root), observation.repository_root)

    def test_directory_outside_repository_is_rejected_clearly(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "inside a repository"):
                LocalGitAdapter(clock=lambda: NOW).repository_root(directory)

    def test_publication_is_exact_expiring_single_use_and_exceptional_refs_fail_closed(self):
        approval = git_schema_values()[3]
        grant = engineering_grant_schema_values()[0]
        provider = _Provider()
        service = GitPublicationService(provider, _Consumptions())
        receipt = service.publish(approval, grant, instant=NOW + timedelta(minutes=1))
        self.assertEqual(approval.proposed_new_object_id, receipt.published_new_object_id)
        with self.assertRaisesRegex(PermissionError, "consumed"):
            service.publish(approval, grant, instant=NOW + timedelta(minutes=1))
        denied = replace(approval, approval_id="force-1", kind=GitPublicationKind.FORCE_PUSH)
        without_protected = replace(
            grant,
            mode=EngineeringDelegationMode.CUSTOM,
            authorities=tuple(item for item in grant.authorities if item.value != "protected_ref_write"),
        )
        with self.assertRaisesRegex(PermissionError, "exceptional"):
            GitPublicationService(provider, _Consumptions()).publish(
                denied, without_protected, instant=NOW + timedelta(minutes=1),
            )

    def test_exact_approved_ignored_generated_path_can_be_staged(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            subprocess.run(("git", "init", "-q", "-b", "main", str(root)), check=True)
            (root / ".gitignore").write_text("docs/\n")
            subprocess.run(
                (
                    "git", "-C", str(root), "-c", "user.name=Fixture",
                    "-c", "user.email=f@x", "add", ".gitignore",
                ),
                check=True,
            )
            subprocess.run(
                (
                    "git", "-C", str(root), "-c", "user.name=Fixture",
                    "-c", "user.email=f@x", "commit", "-qm", "initial",
                ),
                check=True,
            )
            generated = root / "docs/generated/fam-architecture.mmd"
            generated.parent.mkdir(parents=True)
            generated.write_text("flowchart LR\n")
            head = subprocess.run(
                ("git", "-C", str(root), "rev-parse", "HEAD"),
                check=True, capture_output=True, text=True,
            ).stdout.strip()
            action = GitLocalAction(
                "stage-ignored-1", "task-1", str(root),
                GitLocalActionKind.STAGE_PATHS, None,
                ("docs/generated/fam-architecture.mmd",), None,
                "change-1", ("verify-1",), head, NOW,
            )

            receipt = LocalGitAdapter(clock=lambda: NOW).apply(action)

            self.assertEqual(
                ("docs/generated/fam-architecture.mmd",),
                receipt.staged_paths,
            )

    def test_publication_consumption_survives_restart(self):
        approval = git_schema_values()[3]
        grant = engineering_grant_schema_values()[0]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "publication.sqlite3"
            first = SQLitePublicationConsumptionStore(path)
            GitPublicationService(_Provider(), first).publish(
                approval, grant, instant=NOW + timedelta(minutes=1),
            )
            first.close()
            second = SQLitePublicationConsumptionStore(path)
            with self.assertRaisesRegex(PermissionError, "consumed"):
                GitPublicationService(_Provider(), second).publish(
                    approval, grant, instant=NOW + timedelta(minutes=1),
                )
            second.close()

    def test_local_git_rejects_metadata_and_nested_repository_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            subprocess.run(("git", "init", "-q", "-b", "main", str(root)), check=True)
            adapter = LocalGitAdapter(clock=lambda: NOW)
            head = None
            for path in (".git/config", ".gitmodules"):
                action = GitLocalAction(
                    f"deny-{path}", "task-1", str(root),
                    GitLocalActionKind.STAGE_PATHS, None, (path,), None,
                    "change-1", ("verify-1",), head, NOW,
                )
                with self.assertRaisesRegex(PermissionError, "metadata|submodule"):
                    adapter.apply(action)


if __name__ == "__main__":
    unittest.main()
