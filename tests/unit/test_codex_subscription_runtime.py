import json
import sys
import tempfile
import unittest
from pathlib import Path

from fam_os.adapters.codex_subscription import (
    CodexSubscriptionError, CodexSubscriptionRuntime,
    CodexSubscriptionSettings,
)
from fam_os.adapters.linux.bounded_command import BoundedCommandResult
from fam_os.core.ports.inference import (
    InferenceMessage, InferenceRequest, MessageRole,
)


class CodexSubscriptionRuntimeTests(unittest.TestCase):
    def test_native_agent_uses_workspace_tools_and_accepts_execution_events(self):
        events = "\n".join((
            json.dumps({"type": "thread.started", "thread_id": "thread-1"}),
            json.dumps({"type": "turn.started"}),
            json.dumps({
                "type": "item.completed",
                "item": {
                    "type": "command_execution", "command": "npm test",
                    "exit_code": 0, "status": "completed",
                },
            }),
            json.dumps({
                "type": "item.completed",
                "item": {"type": "file_change", "changes": []},
            }),
            json.dumps({
                "type": "item.completed",
                "item": {"type": "agent_message", "text": "Implemented and tested."},
            }),
            json.dumps({
                "type": "turn.completed",
                "usage": {"input_tokens": 42, "output_tokens": 9},
            }),
        ))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "candidate"
            workspace.mkdir()
            runner = _Runner(BoundedCommandResult(0, events, ""))
            runtime = CodexSubscriptionRuntime(_settings(root), runner)

            result = runtime.execute_engineering_agent(
                "finish the app", workspace, writable=True,
            )

            command, cwd, environment, prompt = runner.calls[0]
            self.assertEqual(workspace.resolve(), cwd)
            self.assertIn("--sandbox", command)
            self.assertIn("workspace-write", command)
            self.assertNotIn("--ignore-user-config", command)
            self.assertIn("npm test", result.successful_commands)
            self.assertEqual("Implemented and tested.", result.content)
            self.assertEqual(b"finish the app", prompt)
            self.assertNotIn("OPENAI_API_KEY", environment)

    def test_returns_last_effect_free_message_with_usage(self):
        with tempfile.TemporaryDirectory() as temporary:
            runner = _Runner(_success('{"operations":[]}'))
            runtime = CodexSubscriptionRuntime(
                _settings(Path(temporary)), runner,
                clock=_Clock((10.0, 12.0)),
            )

            response = runtime.chat(_request())

            self.assertEqual('{"operations":[]}', response.content)
            self.assertEqual(120, response.metrics.prompt_tokens)
            self.assertEqual(8, response.metrics.output_tokens)
            self.assertEqual(2.0, response.metrics.wall_seconds)
            command = runner.calls[0][0]
            self.assertNotIn("private repository evidence", command)
            self.assertIn("--ephemeral", command)
            self.assertIn("--ignore-user-config", command)
            self.assertIn('approval_policy="never"', command)
            self.assertIn('web_search="disabled"', command)
            self.assertIn(
                'permissions.fam_inference.filesystem.:minimal="read"', command,
            )
            self.assertEqual("-", command[-1])
            environment = runner.calls[0][2]
            self.assertEqual(
                {"HOME", "PATH", "LANG", "LC_ALL", "NO_COLOR", "TERM"},
                set(environment),
            )
            self.assertNotIn("OPENAI_API_KEY", environment)
            self.assertEqual(Path(temporary) / "work", runner.calls[0][1])
            prompt = json.loads(
                runner.calls[0][3].decode().split("\n", 1)[1]
            )
            self.assertEqual(
                "private repository evidence",
                prompt["messages"][1]["content"],
            )

    def test_rejects_tool_activity_even_when_process_succeeds(self):
        events = "\n".join((
            json.dumps({"type": "thread.started", "thread_id": "thread-1"}),
            json.dumps({"type": "turn.started"}),
            json.dumps({
                "type": "item.completed",
                "item": {"type": "command_execution", "command": "pwd"},
            }),
            json.dumps({
                "type": "turn.completed",
                "usage": {"input_tokens": 1, "output_tokens": 1},
            }),
        ))
        with tempfile.TemporaryDirectory() as temporary:
            runtime = CodexSubscriptionRuntime(
                _settings(Path(temporary)),
                _Runner(BoundedCommandResult(0, events, "")),
            )
            with self.assertRaisesRegex(
                CodexSubscriptionError, "tool_activity_rejected",
            ):
                runtime.chat(_request())

    def test_fails_closed_for_model_mismatch_timeout_and_images(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            timeout = CodexSubscriptionRuntime(
                _settings(root),
                _Runner(BoundedCommandResult(None, "", "", timed_out=True)),
            )
            with self.assertRaisesRegex(CodexSubscriptionError, "timed_out"):
                timeout.chat(_request())
            with self.assertRaisesRegex(CodexSubscriptionError, "model_binding"):
                timeout.chat(_request(model_ref="different"))
            image_request = InferenceRequest(
                "gpt-5.6-sol",
                (InferenceMessage(MessageRole.USER, "inspect", (b"image",)),),
                1_024, 512,
            )
            with self.assertRaisesRegex(CodexSubscriptionError, "image_input"):
                timeout.chat(image_request)


def _settings(root: Path) -> CodexSubscriptionSettings:
    return CodexSubscriptionSettings(
        Path(sys.executable), root / "work", Path.home(),
    )


def _request(model_ref="gpt-5.6-sol") -> InferenceRequest:
    return InferenceRequest(
        model_ref,
        (
            InferenceMessage(MessageRole.SYSTEM, "return strict JSON"),
            InferenceMessage(MessageRole.USER, "private repository evidence"),
        ),
        2_048, 1_024, json_output=True,
    )


def _success(content: str) -> BoundedCommandResult:
    events = "\n".join((
        json.dumps({"type": "thread.started", "thread_id": "thread-1"}),
        json.dumps({"type": "turn.started"}),
        json.dumps({
            "type": "item.completed",
            "item": {"type": "agent_message", "text": content},
        }),
        json.dumps({
            "type": "turn.completed",
            "usage": {"input_tokens": 120, "output_tokens": 8},
        }),
    ))
    return BoundedCommandResult(0, events, "warning without disclosure")


class _Runner:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def run(self, command, cwd=None, environment=None, input_bytes=None):
        self.calls.append((command, cwd, environment, input_bytes))
        return self.result


class _Clock:
    def __init__(self, values):
        self.values = iter(values)

    def __call__(self):
        return next(self.values)


if __name__ == "__main__":
    unittest.main()
