import unittest
from datetime import datetime, timezone

from fam_os.core.contracts import ResultStatus
from fam_os.shell import (
    ShellApprovalRequest,
    ShellContext,
    ShellContextKind,
    ShellController,
    ShellDecision,
    ShellPlanStep,
    ShellResult,
    ShellRunState,
    ShellSessionSnapshot,
    ShellStepState,
    TerminalShell,
    render_contexts,
    render_snapshot,
)
from fam_os.shell.state import accept_snapshot


class ShellContractTests(unittest.TestCase):
    def test_result_release_and_snapshot_authority_invariants_fail_closed(self):
        with self.assertRaises(ValueError):
            ShellResult("request-1", ResultStatus.FAILED, "unsafe", "failed")
        with self.assertRaises(ValueError):
            snapshot(ShellRunState.WAITING_APPROVAL, 1)
        with self.assertRaises(ValueError):
            snapshot(ShellRunState.RUNNING, 1, approval=approval())
        with self.assertRaises(ValueError):
            ShellSessionSnapshot(
                "session-1", "request-1", 1, ShellRunState.TERMINAL,
                steps=(step(ShellStepState.ACTIVE),), current_step_id="work",
                result=successful_result(),
            )

    def test_reducer_is_monotonic_and_terminal_absorbing(self):
        first = snapshot(ShellRunState.ACCEPTED, 0)
        running = snapshot(
            ShellRunState.RUNNING, 1,
            steps=(step(ShellStepState.ACTIVE),), current_step_id="work",
        )
        self.assertEqual(running, accept_snapshot(first, running))
        with self.assertRaisesRegex(ValueError, "revision regressed"):
            accept_snapshot(running, first)
        terminal = snapshot(
            ShellRunState.TERMINAL, 2,
            steps=(step(ShellStepState.SUCCEEDED),), current_step_id="work",
            result=successful_result(),
        )
        with self.assertRaisesRegex(ValueError, "absorbing"):
            accept_snapshot(terminal, snapshot(ShellRunState.ACCEPTED, 3))


class ShellControllerTests(unittest.TestCase):
    def test_context_ask_progress_approval_and_result_flow(self):
        client = ScriptedClient()
        controller = ShellController(client, request_id_factory=lambda: "request-1")
        controller.add_context(ShellContext(
            "context-1", ShellContextKind.APPLICATION, "app:vscode", "VS Code",
            ("editor.observe",),
        ))

        accepted = controller.ask("Explain this project", verification_required=True)
        self.assertEqual(ShellRunState.ACCEPTED, accepted.state)
        self.assertEqual(("editor.observe",), client.ask_command.required_capabilities)
        self.assertTrue(client.ask_command.verification_required)

        waiting = controller.refresh()
        self.assertEqual(ShellRunState.WAITING_APPROVAL, waiting.state)
        terminal = controller.decide(ShellDecision.APPROVE)
        self.assertEqual(ShellRunState.TERMINAL, terminal.state)
        self.assertEqual("approval-1", client.decision.approval_id)
        self.assertEqual(1, client.decision.expected_revision)

    def test_cancellation_is_revision_bound(self):
        client = ScriptedClient()
        controller = ShellController(client, request_id_factory=lambda: "request-1")
        controller.ask("Work")
        terminal = controller.cancel()
        self.assertEqual(ShellRunState.TERMINAL, terminal.state)
        self.assertEqual(0, client.cancellation.expected_revision)

    def test_context_is_frozen_during_active_request(self):
        controller = ShellController(ScriptedClient(), request_id_factory=lambda: "request-1")
        controller.ask("Work")
        with self.assertRaisesRegex(RuntimeError, "context is frozen"):
            controller.add_context(ShellContext(
                "context-1", ShellContextKind.FILE, "file:/notes", "Notes"
            ))


class ShellTerminalTests(unittest.TestCase):
    def test_plain_terminal_covers_context_ask_status_and_approval(self):
        client = ScriptedClient()
        controller = ShellController(client, request_id_factory=lambda: "request-1")
        shell = TerminalShell(controller, context_id_factory=lambda: "context-1")
        output, _ = shell.execute(
            'context add application app:vscode "VS Code" editor.observe'
        )
        self.assertEqual("Context added: context-1", output)
        output, _ = shell.execute("ask --verify Explain this project")
        self.assertIn("State: accepted", output)
        output, _ = shell.execute("refresh")
        self.assertIn("Approval required:", output)
        self.assertIn("Enter 'approve' or 'deny'.", output)
        output, _ = shell.execute("approve")
        self.assertIn("Result: verified", output)
        self.assertIn("Safe answer", output)

    def test_renderer_uses_display_name_not_resource_reference(self):
        context = ShellContext(
            "context-1", ShellContextKind.FILE, "file:///private/path", "Notes"
        )
        rendered = render_contexts((context,))
        self.assertIn("Notes", rendered)
        self.assertNotIn("private/path", rendered)

    def test_renderer_neutralizes_terminal_control_sequences(self):
        result = ShellResult(
            "request-1", ResultStatus.COMPLETED, "answer\x1b[2J\nnext"
        )
        rendered = render_snapshot(snapshot(
            ShellRunState.TERMINAL, 2, result=result
        ))
        self.assertNotIn("\x1b", rendered)
        self.assertIn("answer�[2J\nnext", rendered)

    def test_client_exception_text_is_not_rendered(self):
        shell = TerminalShell(ShellController(FailingClient()))
        output, _ = shell.execute("ask hello")
        self.assertEqual("Command could not be completed safely.", output)
        self.assertNotIn("secret", output)


class ScriptedClient:
    def __init__(self):
        self.ask_command = None
        self.decision = None
        self.cancellation = None

    def ask(self, command):
        self.ask_command = command
        return snapshot(ShellRunState.ACCEPTED, 0)

    def snapshot(self, session_id):
        return snapshot(
            ShellRunState.WAITING_APPROVAL, 1,
            steps=(step(ShellStepState.ACTIVE),), current_step_id="work",
            approval=approval(), message="Ready for approval",
        )

    def decide(self, command):
        self.decision = command
        return snapshot(
            ShellRunState.TERMINAL, 2,
            steps=(step(ShellStepState.SUCCEEDED),), current_step_id="work",
            result=successful_result(), message="Verified",
        )

    def cancel(self, command):
        self.cancellation = command
        result = ShellResult("request-1", ResultStatus.WITHHELD, None, "Cancelled")
        return snapshot(ShellRunState.TERMINAL, command.expected_revision + 1, result=result)


class FailingClient:
    def ask(self, command):
        raise RuntimeError("secret provider error")


def snapshot(state, revision, **values):
    return ShellSessionSnapshot("session-1", "request-1", revision, state, **values)


def step(state):
    return ShellPlanStep("work", "inference", "Do the work", state)


def approval():
    return ShellApprovalRequest(
        "approval-1", "proposal-1", "editor.write", "Update the editor",
        datetime(2026, 7, 17, tzinfo=timezone.utc), False,
    )


def successful_result():
    return ShellResult(
        "request-1", ResultStatus.VERIFIED, "Safe answer",
        verified=True, evidence_ids=("test-1",),
    )


if __name__ == "__main__":
    unittest.main()
