import json
import tempfile
import time
import unittest
from pathlib import Path

from fam_os.core.agent import AgentAuthorityProfile
from fam_os.core.ports.inference import InferenceMetrics, InferenceResponse
from fam_os.product.goal_mode import GoalModeService


class _Runtime:
    def chat(self, request):
        return InferenceResponse(json.dumps({
            "title": "Build the browser game",
            "steps": ["Inspect the workspace", "Implement the game", "Verify behavior"],
            "acceptance_criteria": ["Game loads", "Controls and collisions work"],
        }), InferenceMetrics(request.model_ref, .1, 0, 10, 20))


class _NaturalEngineering:
    owner_id = "owner"

    def __init__(self):
        self.activations = 0
        self.applied = []
        self.controls = []
        self.thread_document = None

    def propose(self, owner_id, prompt, workspace, **kwargs):
        return {"proposal_id": "proposal-1"}

    def activate(self, owner_id, proposal_id, session_id, **kwargs):
        self.activations += 1
        return {"engineering_task": {
            "outcome": "changeset_approval_required",
            "pending_changeset_id": "changeset-1",
        }}

    def approve_changeset(
        self, owner_id, proposal_id, changeset_id, session_id, **kwargs,
    ):
        self.applied.append(changeset_id)
        return {"engineering_task": {"outcome": "completed"}}

    def control_thread(self, owner_id, session_id, workspace, kind, content):
        self.controls.append((kind, content))

    def thread(self, owner_id, session_id, workspace):
        if self.thread_document is None:
            raise LookupError("no active thread")
        return self.thread_document


class GoalModeTests(unittest.TestCase):
    def test_goal_is_planned_activated_in_background_and_applied(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api = _NaturalEngineering()
            service = GoalModeService(
                root / "goals.sqlite3", api, _Runtime(), "model", poll_seconds=.01,
            )
            goal = service.prepare(
                "owner", "Build a complete browser game", str(root),
                AgentAuthorityProfile.WORKSPACE, "session",
            )
            self.assertEqual("draft", goal["status"])
            self.assertEqual(3, len(goal["plan"]))
            service.start()
            accepted = service.activate("owner", goal["goal_id"], confirmed=True)
            self.assertIn(accepted["status"], {"queued", "running", "completed"})

            completed = _wait(service, goal["goal_id"], "completed")

            self.assertEqual("completed", completed["status"])
            self.assertEqual(1, completed["epochs"])
            self.assertEqual(["changeset-1"], api.applied)
            service.stop()

    def test_running_goal_is_requeued_after_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "goals.sqlite3"
            first = GoalModeService(path, _NaturalEngineering(), _Runtime(), "model")
            goal = first.prepare(
                "owner", "Build a complete browser game", str(root),
                AgentAuthorityProfile.WORKSPACE, "session",
            )
            first._database.execute(
                "UPDATE engineering_goals SET status='running' WHERE goal_id=?",
                (goal["goal_id"],),
            )
            first._database.commit()
            first._database.close()

            second_api = _NaturalEngineering()
            second = GoalModeService(path, second_api, _Runtime(), "model", poll_seconds=.01)
            second.start()
            completed = _wait(second, goal["goal_id"], "completed")

            self.assertEqual("completed", completed["status"])
            self.assertEqual(1, second_api.activations)
            second.stop()

    def test_queued_goal_can_pause_resume_and_cancel(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            service = GoalModeService(
                root / "goals.sqlite3", _NaturalEngineering(), _Runtime(), "model",
            )
            goal = service.prepare(
                "owner", "Build a complete browser game", str(root),
                AgentAuthorityProfile.WORKSPACE, "session",
            )
            service.activate("owner", goal["goal_id"], confirmed=True)
            paused = service.control("owner", goal["goal_id"], "pause")
            self.assertEqual("paused", paused["status"])
            resumed = service.control("owner", goal["goal_id"], "resume")
            self.assertEqual("queued", resumed["status"])
            cancelled = service.control("owner", goal["goal_id"], "cancel")
            self.assertEqual("cancelled", cancelled["status"])
            service.stop()

    def test_running_goal_accepts_guidance_for_the_next_model_step(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api = _NaturalEngineering()
            service = GoalModeService(
                root / "goals.sqlite3", api, _Runtime(), "model",
            )
            goal = service.prepare(
                "owner", "Build a complete browser game", str(root),
                AgentAuthorityProfile.WORKSPACE, "session",
            )
            service._database.execute(
                "UPDATE engineering_goals SET status='running' WHERE goal_id=?",
                (goal["goal_id"],),
            )
            service._database.commit()

            service.control(
                "owner", goal["goal_id"], "guide", "Prioritize mobile controls.",
            )

            self.assertEqual("steer", api.controls[-1][0])
            self.assertIn("mobile controls", api.controls[-1][1])
            service.stop()

    def test_inspect_exposes_compact_live_agent_progress(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api = _NaturalEngineering()
            service = GoalModeService(
                root / "goals.sqlite3", api, _Runtime(), "model",
            )
            goal = service.prepare(
                "owner", "Build a complete browser game", str(root),
                AgentAuthorityProfile.WORKSPACE, "session",
            )
            service._database.execute(
                "UPDATE engineering_goals SET status='running' WHERE goal_id=?",
                (goal["goal_id"],),
            )
            service._database.commit()
            api.thread_document = {
                "latest_checkpoint": {
                    "node": "execute", "phase": "implementation", "step": 7,
                    "sequence": 22, "state": {
                        "model_ref": "qwen:27b", "escalated": True,
                        "result_count": 3, "tool_count": 4,
                    },
                },
                "turns": [{
                    "turn_id": "turn-1", "status": "running",
                    "events": [{
                        "call_id": "call-1", "tool_id": "write_file",
                        "event_kind": "result", "created_at": "now",
                        "payload": {
                            "succeeded": True, "output": "created",
                            "postcondition": {"path": "src/game.js", "exists": True},
                        },
                    }],
                }],
            }

            inspected = service.inspect("owner", goal["goal_id"])

            self.assertEqual(7, inspected["live"]["step"])
            self.assertEqual("qwen:27b", inspected["live"]["model_ref"])
            self.assertEqual(["src/game.js"], inspected["live"]["changed_files"])
            self.assertEqual(1, len(inspected["live"]["events"]))
            service.stop()


def _wait(service, goal_id, expected):
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        goal = service.inspect("owner", goal_id)
        if goal["status"] == expected:
            return goal
        time.sleep(.01)
    raise AssertionError(service.inspect("owner", goal_id))


if __name__ == "__main__":
    unittest.main()
