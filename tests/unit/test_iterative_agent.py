import json
import os
import tempfile
import unittest
from pathlib import Path

from fam_os.core.agent import (
    AgentAuthorityProfile,
    AgentToolCall,
    AgentToolDescriptor,
    AgentToolEffect,
    AgentToolExecution,
    AgentToolRegistry,
    IterativeAgentSettings,
    IterativeModelAgent,
)
from fam_os.core.ports.inference import InferenceResponse
from fam_os.core.ports.inference import InferenceToolCall, MessageRole
from fam_os.product.agent_turn_store import SQLiteAgentTurnStore
from fam_os.product.storage.database import ProductionDatabase, StorageSettings
from fam_os.core.agent.runtime import AgentTurnCancelled
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


class _NativeRuntime:
    supports_native_tools = True

    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def chat(self, request):
        self.requests.append(request)
        return self.responses.pop(0)


class IterativeAgentTests(unittest.TestCase):
    def test_semantic_filesystem_postcondition_completes_without_verify_command(self):
        metrics = InferenceMetrics("model", 0, 0, 1, 1)
        runtime = _NativeRuntime([
            InferenceResponse("", metrics, (
                InferenceToolCall(
                    "create-1", "create_directory", {"path": "reports"},
                ),
            )),
            InferenceResponse("Created reports and verified it exists.", metrics),
        ])
        tools = AgentToolRegistry()
        tools.register(
            AgentToolDescriptor(
                "create_directory", "Create a directory.",
                AgentToolEffect.WORKSPACE_WRITE, {
                    "type": "object", "properties": {
                        "path": {"type": "string"},
                    }, "required": ["path"],
                },
            ),
            lambda arguments: AgentToolExecution(
                f"created {arguments['path']}", {
                    "verified": True, "exists": True, "kind": "directory",
                    "path": arguments["path"],
                },
            ),
        )
        tools.register(
            _tool("verify_command", AgentToolEffect.COMMAND), lambda _: "passed",
        )

        outcome = IterativeModelAgent(
            runtime, IterativeAgentSettings("model"), tools, _Store(),
            completion_validator=lambda results: (
                None if any(
                    item.postcondition and item.postcondition.get("verified")
                    for item in results
                ) else "verified effect required"
            ),
        ).run(
            thread_id="thread", turn_id="turn", objective="Create reports.",
            profile=AgentAuthorityProfile.WORKSPACE,
        )

        self.assertEqual(2, outcome.model_steps)
        self.assertTrue(outcome.tool_results[0].postcondition["verified"])
        self.assertIn(
            "verify_command", {item.name for item in runtime.requests[1].tools},
        )

    def test_large_successful_tool_output_is_truncated_not_rejected(self):
        tools = AgentToolRegistry()
        tools.register(
            _tool("large_output", AgentToolEffect.OBSERVE),
            lambda _: "x" * 300_000,
        )

        result = tools.invoke(
            AgentToolCall("call-large", "large_output", {}, "test"),
            AgentAuthorityProfile.ASK,
        )

        self.assertTrue(result.succeeded)
        self.assertLessEqual(len(result.output.encode("utf-8")), 262_144)
        self.assertTrue(result.output.endswith("[tool output truncated by FAM_OS]"))

    def test_native_tool_protocol_uses_runtime_tools_and_tool_role_results(self):
        metrics = InferenceMetrics("model", 0, 0, 1, 1)
        runtime = _NativeRuntime([
            InferenceResponse("", metrics, (
                InferenceToolCall("native-1", "read_file", {"path": "README.md"}),
            )),
            InferenceResponse("README.md contains the project overview.", metrics),
        ])
        tools = AgentToolRegistry()
        tools.register(
            AgentToolDescriptor(
                "read_file", "Read a file.", AgentToolEffect.OBSERVE,
                {"type": "object", "properties": {
                    "path": {"type": "string"},
                }, "required": ["path"]},
            ),
            lambda arguments: f"content of {arguments['path']}",
        )
        tools.register(
            _tool("verify_command", AgentToolEffect.COMMAND), lambda _: "passed",
        )

        outcome = IterativeModelAgent(
            runtime, IterativeAgentSettings("model"), tools, _Store(),
        ).run(
            thread_id="thread", turn_id="turn", objective="Read README.md.",
            profile=AgentAuthorityProfile.ASK,
        )

        self.assertEqual("README.md contains the project overview.",
                         outcome.response.content)
        self.assertEqual("read_file", runtime.requests[0].tools[0].name)
        self.assertNotIn(
            "verify_command", {item.name for item in runtime.requests[0].tools},
        )
        self.assertNotIn(
            "verify_command", {item.name for item in runtime.requests[1].tools},
        )
        self.assertEqual("auto", runtime.requests[0].tool_choice)
        self.assertFalse(runtime.requests[0].json_output)
        self.assertEqual(MessageRole.TOOL, runtime.requests[1].messages[-1].role)
        self.assertEqual("native-1", runtime.requests[1].messages[-1].tool_call_id)

    def test_large_conversation_history_is_compacted_before_inference(self):
        metrics = InferenceMetrics("model", 0, 0, 1, 1)
        runtime = _NativeRuntime([
            InferenceResponse("Done from current objective.", metrics),
        ])

        IterativeModelAgent(
            runtime,
            IterativeAgentSettings(
                "qwen2.5-coder:7b", context_tokens=8_192,
                maximum_output_tokens=2_048,
            ),
            AgentToolRegistry(), _HistoryStore("old history " * 10_000),
        ).run(
            thread_id="thread", turn_id="turn", objective="Current objective.",
            profile=AgentAuthorityProfile.ASK,
        )

        content = "\n".join(item.content for item in runtime.requests[0].messages)
        self.assertIn("Current objective.", content)
        self.assertLess(len(content.encode("utf-8")), 20_000)

    def test_sqlite_store_delivers_durable_owner_controls_once(self):
        with tempfile.TemporaryDirectory() as directory:
            database = ProductionDatabase(StorageSettings(
                Path(directory) / "state.sqlite3", os.geteuid(),
            ))
            database.open()
            try:
                store = SQLiteAgentTurnStore(database, "/workspace")
                store.begin_turn(
                    "thread", "turn", "Implement it.",
                    AgentAuthorityProfile.WORKSPACE,
                )
                store.request_control("thread", "steer", "Preserve compatibility.")
                self.assertEqual(
                    ({"kind": "steer", "content": "Preserve compatibility."},),
                    store.consume_controls("thread"),
                )
                self.assertEqual((), store.consume_controls("thread"))
            finally:
                database.close()

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

                follow_up = _Runtime([
                    {"type": "final", "content": "Used the earlier result."},
                ])
                IterativeModelAgent(
                    follow_up, IterativeAgentSettings("model"), tools, store,
                ).run(
                    thread_id="thread-1", turn_id="turn-2",
                    objective="Continue from that change.",
                    profile=AgentAuthorityProfile.WORKSPACE,
                )
                initial = json.loads(follow_up.requests[0].messages[-1].content)
                self.assertIn("Implement the feature.", initial["conversation_history"])
                self.assertIn(
                    "Implemented and verified the change.",
                    initial["conversation_history"],
                )
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

    def test_grounding_reviewer_rejects_unrelated_final_and_requests_resynthesis(self):
        runtime = _Runtime([
            {"type": "tool_call", "tool": "list_directory", "arguments": {},
             "reason": "List the requested folder."},
            {"type": "final", "content": "Python is unavailable."},
            {"type": "final", "content": "The folder contains README.md."},
        ])
        tools = AgentToolRegistry()
        tools.register(
            _tool("list_directory", AgentToolEffect.OBSERVE),
            lambda _: "file\tREADME.md",
        )
        reviews = []

        def review(_objective, response, _results):
            reviews.append(response.content)
            return (
                "The answer is unrelated to the requested folder listing."
                if "Python" in response.content else None
            )

        outcome = IterativeModelAgent(
            runtime, IterativeAgentSettings("model"), tools, _Store(),
            completion_reviewer=review,
        ).run(
            thread_id="thread", turn_id="turn", objective="What's inside?",
            profile=AgentAuthorityProfile.ASK,
        )

        self.assertEqual("The folder contains README.md.", outcome.response.content)
        self.assertEqual(2, len(reviews))
        self.assertIn("completion_rejected", runtime.requests[2].messages[-1].content)

    def test_repeated_tool_call_is_not_reexecuted_and_requests_new_strategy(self):
        repeated = {"type": "tool_call", "tool": "inspect", "arguments": {},
                    "reason": "Try the same observation."}
        runtime = _Runtime([
            repeated, repeated, repeated,
            {"type": "final", "content": "Changed strategy."},
        ])
        calls = []
        tools = AgentToolRegistry()
        tools.register(
            _tool("inspect", AgentToolEffect.OBSERVE),
            lambda _: calls.append(True) or "same",
        )

        outcome = IterativeModelAgent(
            runtime, IterativeAgentSettings("model"), tools, _Store(),
        ).run(
            thread_id="thread", turn_id="turn", objective="Inspect.",
            profile=AgentAuthorityProfile.ASK,
        )

        self.assertEqual(2, len(calls))
        self.assertFalse(outcome.tool_results[2].succeeded)
        self.assertIn("loop detected", outcome.tool_results[2].output.lower())
        self.assertEqual(
            "system", runtime.requests[3].messages[-1].role.value,
        )
        self.assertIn("blocked for the remainder", runtime.requests[3].messages[-1].content)

    def test_repeated_tool_call_does_not_abort_turn_before_model_recovers(self):
        repeated = {"type": "tool_call", "tool": "inspect", "arguments": {},
                    "reason": "Retry the unavailable approach."}
        runtime = _Runtime([
            repeated, repeated, repeated, repeated, repeated, repeated,
            {"type": "final", "content": "The optional tool is unavailable; used existing evidence."},
        ])
        calls = []
        tools = AgentToolRegistry()
        tools.register(
            _tool("inspect", AgentToolEffect.OBSERVE),
            lambda _: calls.append(True) or "unavailable",
        )

        outcome = IterativeModelAgent(
            runtime, IterativeAgentSettings("model"), tools, _Store(),
        ).run(
            thread_id="thread", turn_id="turn", objective="Inspect.",
            profile=AgentAuthorityProfile.ASK,
        )

        self.assertEqual(7, outcome.model_steps)
        self.assertEqual(2, len(calls))
        self.assertEqual("The optional tool is unavailable; used existing evidence.",
                         outcome.response.content)

    def test_owner_guidance_is_injected_before_the_next_model_step(self):
        runtime = _Runtime([
            {"type": "final", "content": "Followed the owner's guidance."},
        ])
        store = _ControlStore([{"kind": "steer", "content": "Keep the API name."}])

        IterativeModelAgent(
            runtime, IterativeAgentSettings("model"), AgentToolRegistry(), store,
        ).run(
            thread_id="thread", turn_id="turn", objective="Refactor the API.",
            profile=AgentAuthorityProfile.WORKSPACE,
        )

        self.assertIn("owner_guidance", runtime.requests[0].messages[-1].content)
        self.assertIn("Keep the API name", runtime.requests[0].messages[-1].content)

    def test_owner_cancel_stops_before_another_model_call(self):
        runtime = _Runtime([])
        store = _ControlStore([{"kind": "cancel", "content": "Stop now."}])

        with self.assertRaisesRegex(AgentTurnCancelled, "Stop now"):
            IterativeModelAgent(
                runtime, IterativeAgentSettings("model"), AgentToolRegistry(), store,
            ).run(
                thread_id="thread", turn_id="turn", objective="Keep working.",
                profile=AgentAuthorityProfile.WORKSPACE,
            )

        self.assertEqual([], runtime.requests)
        self.assertEqual("Stop now.", store.cancelled)


class _Store:
    def begin_turn(self, *args): pass
    def record_call(self, *args): pass
    def record_result(self, *args): pass
    def complete_turn(self, *args): pass
    def fail_turn(self, *args): pass


class _HistoryStore(_Store):
    def __init__(self, history):
        self.history = history

    def conversation_context(self, _thread_id):
        return self.history


class _ControlStore(_Store):
    def __init__(self, controls):
        self.controls = tuple(controls)
        self.cancelled = None

    def consume_controls(self, _thread_id):
        controls, self.controls = self.controls, ()
        return controls

    def cancel_turn(self, _thread_id, _turn_id, reason):
        self.cancelled = reason


def _tool(tool_id, effect):
    return AgentToolDescriptor(
        tool_id, tool_id.replace("_", " "), effect,
        {"type": "object", "properties": {}},
    )


if __name__ == "__main__":
    unittest.main()
