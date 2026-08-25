import json
import tempfile
import threading
import time
import unittest
from pathlib import Path

from fam_os.core.agent import AgentAuthorityProfile
from fam_os.core.ports.inference import (
    InferenceMetrics, InferenceResponse, TransientInferenceError,
)
from fam_os.product.goal_mode import GoalModeService


class _Runtime:
    def __init__(self, failures=0):
        self.failures = failures

    def chat(self, request):
        if self.failures:
            self.failures -= 1
            raise TransientInferenceError("planner disconnected")
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
        self.activation_failures = 0
        self.apply_failures = 0

    def propose(self, owner_id, prompt, workspace, **kwargs):
        return {"proposal_id": "proposal-1"}

    def activate(self, owner_id, proposal_id, session_id, **kwargs):
        self.activations += 1
        if self.activation_failures:
            self.activation_failures -= 1
            raise TransientInferenceError("model disconnected")
        return {"engineering_task": {
            "outcome": "changeset_approval_required",
            "pending_changeset_id": "changeset-1",
        }}

    def approve_changeset(
        self, owner_id, proposal_id, changeset_id, session_id, **kwargs,
    ):
        if self.apply_failures:
            self.apply_failures -= 1
            raise TransientInferenceError("apply response interrupted")
        self.applied.append(changeset_id)
        return {"engineering_task": {"outcome": "completed"}}

    def control_thread(self, owner_id, session_id, workspace, kind, content):
        self.controls.append((kind, content))

    def thread(self, owner_id, session_id, workspace):
        if self.thread_document is None:
            raise LookupError("no active thread")
        return self.thread_document


class GoalModeTests(unittest.TestCase):
    def test_planning_recovers_from_transient_model_disconnect(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = _Runtime(failures=2)
            service = GoalModeService(
                root / "goals.sqlite3", _NaturalEngineering(), runtime, "model",
                retry_base_seconds=.001, retry_max_seconds=.002,
                sleeper=lambda _seconds: None,
            )

            goal = service.prepare(
                "owner", "Build a complete browser game", str(root),
                AgentAuthorityProfile.WORKSPACE, "session",
            )

            self.assertEqual("draft", goal["status"])
            self.assertEqual(0, runtime.failures)
            service.stop()

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
                            "succeeded": True,
                            "output": "create_file\tsrc/game.js",
                            "postcondition": {"path": "src/game.js", "exists": True},
                        },
                    }, {
                        "call_id": "call-2", "tool_id": "run_command",
                        "event_kind": "result", "created_at": "later",
                        "payload": {
                            "succeeded": True,
                            "output": "status=completed\nrecorded_filesystem_effects:"
                                      "\ncreate_file\tpackage-lock.json"
                                      "\npatch_file\tpackage.json",
                            "postcondition": None,
                        },
                    }],
                }],
            }

            inspected = service.inspect("owner", goal["goal_id"])

            self.assertEqual(7, inspected["live"]["step"])
            self.assertEqual("qwen:27b", inspected["live"]["model_ref"])
            self.assertEqual(
                ["package-lock.json", "package.json", "src/game.js"],
                inspected["live"]["changed_files"],
            )
            self.assertEqual(2, len(inspected["live"]["events"]))
            service.stop()

    def test_transient_activation_failure_retries_and_completes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api = _NaturalEngineering()
            api.activation_failures = 2
            service = GoalModeService(
                root / "goals.sqlite3", api, _Runtime(), "model",
                poll_seconds=.005, retry_base_seconds=.005,
                retry_max_seconds=.01, watchdog_seconds=.1,
            )
            goal = service.prepare(
                "owner", "Build a complete browser game", str(root),
                AgentAuthorityProfile.WORKSPACE, "session",
            )
            service.start()
            service.activate("owner", goal["goal_id"], confirmed=True)

            completed = _wait(service, goal["goal_id"], "completed")

            self.assertEqual(3, api.activations)
            self.assertEqual(2, completed["recovery"]["attempt"])
            self.assertEqual(["changeset-1"], api.applied)
            service.stop()

    def test_transient_final_apply_retries_exact_changeset_without_reactivation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api = _NaturalEngineering()
            api.apply_failures = 1
            service = GoalModeService(
                root / "goals.sqlite3", api, _Runtime(), "model",
                poll_seconds=.005, retry_base_seconds=.005,
                retry_max_seconds=.005,
            )
            goal = service.prepare(
                "owner", "Build a complete browser game", str(root),
                AgentAuthorityProfile.WORKSPACE, "session",
            )
            service.start()
            service.activate("owner", goal["goal_id"], confirmed=True)

            completed = _wait(service, goal["goal_id"], "completed")

            self.assertEqual(1, api.activations)
            self.assertEqual(["changeset-1"], api.applied)
            self.assertEqual("complete", completed["recovery"]["stage"])
            service.stop()

    def test_retry_wait_survives_service_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "goals.sqlite3"
            api = _NaturalEngineering()
            api.activation_failures = 1
            first = GoalModeService(
                path, api, _Runtime(), "model", poll_seconds=.005,
                retry_base_seconds=60, retry_max_seconds=60,
            )
            goal = first.prepare(
                "owner", "Build a complete browser game", str(root),
                AgentAuthorityProfile.WORKSPACE, "session",
            )
            first.start()
            first.activate("owner", goal["goal_id"], confirmed=True)
            waiting = _wait(first, goal["goal_id"], "retry_wait")
            self.assertEqual(1, waiting["recovery"]["attempt"])
            first.stop()

            second = GoalModeService(
                path, api, _Runtime(), "model", poll_seconds=.005,
                retry_base_seconds=.005, retry_max_seconds=.005,
            )
            second._database.execute(
                "UPDATE engineering_goals SET next_retry_at=? WHERE goal_id=?",
                ("2000-01-01T00:00:00+00:00", goal["goal_id"]),
            )
            second._database.commit()
            second.start()
            completed = _wait(second, goal["goal_id"], "completed")
            self.assertEqual("completed", completed["status"])
            second.stop()

    def test_recovery_budget_exhaustion_is_terminal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api = _NaturalEngineering()
            api.activation_failures = 3
            service = GoalModeService(
                root / "goals.sqlite3", api, _Runtime(), "model",
                poll_seconds=.005, retry_base_seconds=.005,
                retry_max_seconds=.005, maximum_recovery_attempts=1,
            )
            goal = service.prepare(
                "owner", "Build a complete browser game", str(root),
                AgentAuthorityProfile.WORKSPACE, "session",
            )
            service.start()
            service.activate("owner", goal["goal_id"], confirmed=True)

            failed = _wait(service, goal["goal_id"], "failed")

            self.assertIn("recovery_budget_exhausted", failed["error"])
            self.assertEqual(2, api.activations)
            service.stop()

    def test_watchdog_recovers_stalled_provider_without_losing_goal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api = _NaturalEngineering()
            released = threading.Event()
            original_activate = api.activate

            def stalled_activate(*args, **kwargs):
                released.wait(timeout=1)
                return original_activate(*args, **kwargs)

            api.activate = stalled_activate
            service = GoalModeService(
                root / "goals.sqlite3", api, _Runtime(), "model",
                poll_seconds=.005, watchdog_seconds=.02,
                provider_recover=released.set,
            )
            goal = service.prepare(
                "owner", "Build a complete browser game", str(root),
                AgentAuthorityProfile.WORKSPACE, "session",
            )
            service.start()
            service.activate("owner", goal["goal_id"], confirmed=True)

            completed = _wait(service, goal["goal_id"], "completed")

            self.assertEqual(1, completed["recovery"]["watchdog_trips"])
            self.assertTrue(released.is_set())
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
