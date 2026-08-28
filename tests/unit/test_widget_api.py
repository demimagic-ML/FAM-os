import tempfile
import unittest
import json
from unittest import mock
from pathlib import Path

from fam_os.product.widget_api import WidgetStatusApi


class _GoalService:
    owner_id = "owner"

    def __init__(self):
        self.calls = []

    def list(self, owner_id):
        self.assert_owner(owner_id)
        return {"goals": [{"goal_id": "goal-1", "status": "running"}]}

    def inspect(self, owner_id, goal_id):
        self.assert_owner(owner_id)
        return {
            "goal_id": goal_id, "status": "running", "title": "Build",
            "created_at": "2026-08-28T10:00:00+00:00",
            "updated_at": "2026-08-28T10:01:00+00:00",
            "plan": ["one"], "acceptance_criteria": ["done"],
            "candidate": {
                "candidate_workspace": str(Path(tempfile.gettempdir())),
                "counts": {"created": 1, "modified": 2, "deleted": 1},
                "entries": [],
            },
            "live": {"phase": "implementation", "step": 1, "model_ref": "qwen", "events": []},
        }

    def prepare(self, owner_id, prompt, workspace, profile, session):
        self.calls.append(("prepare", owner_id, prompt, workspace, profile.value, session))
        return {"goal_id": "goal-new"}

    def activate(self, owner_id, goal_id, *, confirmed):
        self.calls.append(("activate", owner_id, goal_id, confirmed))
        return {"goal_id": goal_id, "status": "queued"}

    def control(self, owner_id, goal_id, action, content):
        return {"owner": owner_id, "goal": goal_id, "action": action, "content": content}

    def assert_owner(self, value):
        if value != self.owner_id:
            raise AssertionError(value)


class WidgetApiTests(unittest.TestCase):
    def test_status_is_compact_and_goal_submit_uses_durable_api(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            service = _GoalService()
            api = WidgetStatusApi(
                service, console_port=9988, runtime_root=root,
                engineering_provider="ollama",
            )
            status = api.status()
            self.assertEqual(status["contractVersion"], "fam.widget/v1")
            self.assertEqual(status["apiVersion"], 1)
            self.assertEqual(status["pluginMinVersion"], "0.1.0")
            self.assertEqual(status["serviceVersion"], "0.1.0")
            self.assertEqual(status["consoleUrl"], "http://127.0.0.1:9988/")
            self.assertEqual(status["goal"]["candidateChanges"], 4)
            self.assertEqual(status["goal"]["provider"], "ollama")
            self.assertGreaterEqual(status["goal"]["elapsedSeconds"], 60)
            result = api.submit("finish", str(root), "workspace", goal_mode=True)
            self.assertEqual(result["status"], "queued")
            self.assertEqual(service.calls[0][0], "prepare")
            self.assertEqual(service.calls[1], ("activate", "owner", "goal-new", True))

    def test_open_candidate_uses_real_candidate_workspace_field(self):
        with tempfile.TemporaryDirectory() as directory:
            service = _GoalService()
            process = type("Process", (), {"pid": 41})()
            calls = []
            api = WidgetStatusApi(
                service, console_port=9988, runtime_root=Path(directory),
                popen=lambda command, **kwargs: calls.append(command) or process,
            )
            original = service.inspect
            service.inspect = lambda owner, goal: {
                **original(owner, goal),
                "candidate": {"candidate_workspace": directory},
            }
            with mock.patch(
                "fam_os.product.widget_api._desktop_open_command",
                return_value=("open", directory),
            ):
                receipt = api.open_candidate("goal-1")
            self.assertEqual(receipt["target"], directory)
            self.assertEqual(calls, [("open", directory)])

    def test_commands_are_idempotent_and_audited_without_guidance_content(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api = WidgetStatusApi(
                _GoalService(), console_port=9988, runtime_root=root,
                state_root=root / "state",
            )
            calls = []
            first = api.execute_command(
                "qml-command-0001", "goal.guidance",
                lambda: calls.append("secret guidance") or {"status": "running"},
                goal_id="goal-1",
            )
            second = api.execute_command(
                "qml-command-0001", "goal.guidance",
                lambda: calls.append("must not run") or {"status": "wrong"},
                goal_id="goal-1",
            )
            self.assertEqual(first, second)
            self.assertEqual(calls, ["secret guidance"])
            audit = api.audit_path.read_text(encoding="utf-8")
            self.assertNotIn("secret guidance", audit)
            record = json.loads(audit)
            self.assertEqual(record["commandId"], "qml-command-0001")
            self.assertEqual(record["action"], "goal.guidance")
            self.assertEqual(api.audit_path.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
