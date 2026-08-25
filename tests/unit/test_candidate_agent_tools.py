import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from fam_os.adapters.filesystem.candidate_workspace import CandidateWorkspaceAdapter
from fam_os.core.agent import AgentAuthorityProfile, AgentToolCall, AgentToolRegistry
from fam_os.core.engineering import CandidateEditStatus
from fam_os.product.candidate_agent_tools import AuthorizedCandidateAgentTools


class _CommandTools:
    def __init__(self, root):
        self.root = root

    def run_command(self, arguments):
        (self.root / "src/app.py").write_text("value = 3\n")
        (self.root / "generated.py").write_text("generated = True\n")
        (self.root / ".venv/bin").mkdir(parents=True)
        (self.root / ".venv/bin/python").write_bytes(b"\x00binary")
        return "status=completed\nexit_code=0"


class _Loop:
    def __init__(self, adapter, candidate):
        self.adapter = adapter
        self.candidate = candidate
        self.records = []

    def current_candidate(self, owner_id, task_id):
        return replace(
            self.candidate, entries=self.adapter.current_entries(self.candidate),
        )

    def edit_candidate(self, owner_id, task_id, **values):
        artifact = values.get("artifact")
        if artifact is not None:
            self.adapter.stage_artifact(self.candidate, artifact, values["content"])
        self.adapter.execute(
            self.candidate, values["operation"],
            {} if artifact is None else {artifact.artifact_id: artifact},
        )
        applied, digest = self.adapter.effect_applied(
            self.candidate, values["operation"], artifact,
        )
        record = SimpleNamespace(
            edit_id=values["edit_id"], operation=values["operation"],
            status=CandidateEditStatus.APPLIED if applied else None,
            after_sha256=digest,
        )
        self.records.append(record)
        return record


class CandidateAgentToolsTests(unittest.TestCase):
    def test_resume_continues_edit_identity_after_durable_candidate_effects(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            owner, transactions = root / "owner", root / "transactions"
            owner.mkdir()
            adapter = CandidateWorkspaceAdapter(owner, transactions)
            candidate = adapter.create("task-resume")
            loop = _Loop(adapter, candidate)
            definition = SimpleNamespace(task=SimpleNamespace(
                task_id="task-resume", max_changed_files=128,
                max_changed_bytes=64 * 1024**2,
            ))
            tools = AuthorizedCandidateAgentTools(
                loop, "owner", "task-resume", "session", "principal",
                definition, SimpleNamespace(candidate=candidate),
                _CommandTools(Path(candidate.candidate_workspace)),
            )
            tools.restore(
                (SimpleNamespace(edit_id="prior-1"), SimpleNamespace(edit_id="prior-2")),
                ("prior verification",),
            )
            registry = AgentToolRegistry()
            tools.register(registry)

            result = _invoke(registry, "write_file", {
                "path": "continued.txt", "content": "continued\n",
            })

            self.assertTrue(result.succeeded, result.output)
            self.assertEqual("agent-edit-task-resume-3", loop.records[-1].edit_id)
            self.assertEqual(3, len(tools.applied_edits))
            self.assertEqual(["prior verification"], tools.successful_verifications)

    def test_writes_and_command_mutations_are_replayed_as_candidate_edits(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            owner, transactions = root / "owner", root / "transactions"
            (owner / "src").mkdir(parents=True)
            (owner / "src/app.py").write_text("value = 1\n")
            adapter = CandidateWorkspaceAdapter(owner, transactions)
            candidate = adapter.create("task")
            loop = _Loop(adapter, candidate)
            definition = SimpleNamespace(task=SimpleNamespace(
                task_id="task", max_changed_files=128,
                max_changed_bytes=64 * 1024**2,
            ))
            preparation = SimpleNamespace(candidate=candidate)
            registry = AgentToolRegistry()
            tools = AuthorizedCandidateAgentTools(
                loop, "owner", "task", "session", "principal",
                definition, preparation,
                _CommandTools(Path(candidate.candidate_workspace)),
            )
            tools.register(registry)

            self.assertNotIn(
                "git_status", {item.tool_id for item in registry.descriptors()},
            )
            schemas = {
                item.tool_id: item.input_schema for item in registry.descriptors()
            }
            self.assertEqual(
                ["path"], schemas["create_directory"]["required"],
            )
            self.assertEqual(
                ["command"], schemas["verify_command"]["required"],
            )

            written = _invoke(registry, "write_file", {
                "path": "src/app.py", "content": "value = 2\n",
            })
            command = _invoke(registry, "verify_command", {
                "command": ["formatter"],
            })

            self.assertTrue(written.succeeded, written.output)
            self.assertTrue(command.succeeded, command.output)
            workspace = Path(candidate.candidate_workspace)
            self.assertEqual("value = 3\n", (workspace / "src/app.py").read_text())
            self.assertEqual(
                "generated = True\n", (workspace / "generated.py").read_text(),
            )
            self.assertTrue((workspace / ".venv/bin/python").exists())
            self.assertGreaterEqual(len(loop.records), 3)
            self.assertEqual(len(loop.records), len(tools.applied_edits))
            self.assertEqual(1, len(tools.successful_verifications))

    def test_create_directory_returns_machine_checked_postcondition(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            owner, transactions = root / "owner", root / "transactions"
            owner.mkdir()
            adapter = CandidateWorkspaceAdapter(owner, transactions)
            candidate = adapter.create("task-directory")
            loop = _Loop(adapter, candidate)
            definition = SimpleNamespace(task=SimpleNamespace(
                task_id="task-directory", max_changed_files=128,
                max_changed_bytes=64 * 1024**2,
            ))
            registry = AgentToolRegistry()
            tools = AuthorizedCandidateAgentTools(
                loop, "owner", "task-directory", "session", "principal",
                definition, SimpleNamespace(candidate=candidate),
                _CommandTools(Path(candidate.candidate_workspace)),
            )
            tools.register(registry)

            result = _invoke(registry, "create_directory", {"path": "reports"})

            self.assertTrue(result.succeeded, result.output)
            self.assertEqual({
                "verified": True, "operation": "create_directory",
                "path": "reports", "exists": True, "kind": "directory",
            }, result.postcondition)
            self.assertEqual(1, len(tools.successful_verifications))


def _invoke(registry, tool, arguments):
    return registry.invoke(
        AgentToolCall("call-" + tool, tool, arguments, "test"),
        AgentAuthorityProfile.WORKSPACE,
    )


if __name__ == "__main__":
    unittest.main()
