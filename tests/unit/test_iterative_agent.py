import json
import os
import tempfile
import unittest
from pathlib import Path

from fam_os.core.agent import (
    AgentAuthorityProfile,
    AgentToolDescriptor,
    AgentToolEffect,
    AgentToolRegistry,
    IterativeAgentSettings,
    IterativeModelAgent,
)
from fam_os.core.ports.inference import InferenceResponse
from fam_os.product.agent_turn_store import SQLiteAgentTurnStore
from fam_os.product.storage.database import ProductionDatabase, StorageSettings
from fam_os.telemetry.contracts import InferenceMetrics


class _Runtime:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def chat(self, request):
        self.requests.append(request)
        return InferenceResponse(
            json.dumps(self.responses.pop(0)),
            InferenceMetrics("model", 0, 0, 1, 1),
        )


class IterativeAgentTests(unittest.TestCase):
    def test_model_observes_tool_result_and_continues_until_complete(self):
        runtime = _Runtime([
            {"type": "tool_call", "tool": "read_file", "arguments": {
                "path": "src/app.py",
            }, "reason": "Inspect the current implementation."},
            {"type": "tool_call", "tool": "apply_patch", "arguments": {
                "patch": "change",
            }, "reason": "Implement the requested change."},
            {"type": "final", "content": "Implemented and verified the change."},
        ])
        tools = AgentToolRegistry()
        tools.register(_tool("read_file", AgentToolEffect.OBSERVE), lambda _: "old")
        tools.register(
            _tool("apply_patch", AgentToolEffect.WORKSPACE_WRITE), lambda _: "applied",
        )
        with tempfile.TemporaryDirectory() as directory:
            Path(directory).chmod(0o700)
            database = ProductionDatabase(StorageSettings(
                Path(directory) / "state.sqlite3", os.geteuid(),
            ))
            database.open()
            try:
                store = SQLiteAgentTurnStore(database, "/workspace")
                outcome = IterativeModelAgent(
                    runtime, IterativeAgentSettings("model"), tools, store,
                ).run(
                    thread_id="thread-1", turn_id="turn-1",
                    objective="Implement the feature.",
                    profile=AgentAuthorityProfile.WORKSPACE,
                )
                self.assertEqual(3, outcome.model_steps)
                self.assertEqual(2, len(outcome.tool_results))
                self.assertIn("old", runtime.requests[1].messages[-1].content)
                self.assertIn("applied", runtime.requests[2].messages[-1].content)
                persisted = store.thread("thread-1")
                self.assertEqual("completed", persisted["turns"][0]["status"])
                self.assertEqual(4, len(persisted["turns"][0]["events"]))
            finally:
                database.close()

    def test_ask_profile_denies_writes_but_returns_result_to_model(self):
        runtime = _Runtime([
            {"type": "tool_call", "tool": "write_file", "arguments": {
                "path": "x", "content": "y",
            }, "reason": "Try the requested write."},
            {"type": "final", "content": "Write authority is required."},
        ])
        tools = AgentToolRegistry()
        calls = []
        tools.register(
            _tool("write_file", AgentToolEffect.WORKSPACE_WRITE),
            lambda arguments: calls.append(arguments) or "written",
        )
        store = _Store()

        outcome = IterativeModelAgent(
            runtime, IterativeAgentSettings("model"), tools, store,
        ).run(
            thread_id="thread", turn_id="turn", objective="Write x.",
            profile=AgentAuthorityProfile.ASK,
        )

        self.assertFalse(outcome.tool_results[0].succeeded)
        self.assertEqual([], calls)
        self.assertIn("does not allow", runtime.requests[1].messages[-1].content)

    def test_rejected_completion_returns_feedback_and_keeps_agent_running(self):
        runtime = _Runtime([
            {"type": "final", "content": "Done."},
            {"type": "tool_call", "tool": "check", "arguments": {},
             "reason": "Verify the result."},
            {"type": "final", "content": "Verified."},
        ])
        tools = AgentToolRegistry()
        tools.register(_tool("check", AgentToolEffect.OBSERVE), lambda _: "passed")
        store = _Store()
        agent = IterativeModelAgent(
            runtime, IterativeAgentSettings("model"), tools, store,
            completion_validator=lambda results: None if results else "verification required",
        )

        outcome = agent.run(
            thread_id="thread", turn_id="turn", objective="Do and verify.",
            profile=AgentAuthorityProfile.WORKSPACE,
        )

        self.assertEqual(3, outcome.model_steps)
        self.assertIn("completion_rejected", runtime.requests[1].messages[-1].content)


class _Store:
    def begin_turn(self, *args): pass
    def record_call(self, *args): pass
    def record_result(self, *args): pass
    def complete_turn(self, *args): pass
    def fail_turn(self, *args): pass


def _tool(tool_id, effect):
    return AgentToolDescriptor(
        tool_id, tool_id.replace("_", " "), effect,
        {"type": "object", "properties": {}},
    )


if __name__ == "__main__":
    unittest.main()
