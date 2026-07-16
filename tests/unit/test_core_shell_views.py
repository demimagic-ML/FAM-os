import unittest

from fam_os.core.contracts import ResultStatus, StepOutcome, TaskResult
from fam_os.core.ingress import accepted_shell_snapshot, project_shell_snapshot
from fam_os.shell import ShellRunState, ShellStepState
from tests.unit.test_core_plan_lifecycle import plan, routed, service


class CoreShellViewTests(unittest.TestCase):
    def test_started_and_progress_snapshots_project_plan_without_prompt_or_policy(self):
        accepted = accepted_shell_snapshot("shell-session", "request-1")
        runtime = service()
        started = runtime.start(routed(), plan()).snapshot
        projected = project_shell_snapshot("shell-session", started, 1)

        self.assertEqual(ShellRunState.ACCEPTED, accepted.state)
        self.assertEqual(ShellRunState.RUNNING, projected.state)
        self.assertEqual(ShellStepState.ACTIVE, projected.steps[0].state)
        self.assertEqual(ShellStepState.PENDING, projected.steps[1].state)
        self.assertFalse(hasattr(projected, "prompt"))

    def test_terminal_projection_releases_only_core_task_result(self):
        runtime = service()
        started = runtime.start(routed(), plan()).snapshot
        terminal = runtime.advance(
            started.instance_id, 0, StepOutcome.SUCCEEDED
        ).snapshot
        result = TaskResult(
            "request-1", ResultStatus.COMPLETED, "Core-released answer",
            plan_id="plan-1",
        )
        projected = project_shell_snapshot(
            "shell-session", terminal, 2, result=result, message="Complete"
        )

        self.assertEqual(ShellRunState.TERMINAL, projected.state)
        self.assertEqual("Core-released answer", projected.result.content)
        self.assertTrue(all(step.state is not ShellStepState.ACTIVE for step in projected.steps))

    def test_nonterminal_result_and_conflicting_authority_states_reject(self):
        started = service().start(routed(), plan()).snapshot
        result = TaskResult(
            "request-1", ResultStatus.COMPLETED, "answer", plan_id="plan-1"
        )
        with self.assertRaisesRegex(ValueError, "terminal"):
            project_shell_snapshot("shell-session", started, 1, result=result)
        with self.assertRaisesRegex(ValueError, "exclusive"):
            project_shell_snapshot(
                "shell-session", started, 1, result=result, cancelling=True
            )


if __name__ == "__main__":
    unittest.main()
