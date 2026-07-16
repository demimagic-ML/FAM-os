import os
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path

from fam_os.adapters.shell import (
    ShellRequestDispatcher,
    UnixShellClientConfiguration,
    UnixShellCoreClient,
    UnixShellServer,
    UnixShellServerConfiguration,
)
from fam_os.applications.transport.auth import PeerAuthorizationPolicy
from fam_os.core.contracts import ResultStatus
from fam_os.shell import (
    ShellApprovalRequest,
    ShellController,
    ShellPlanStep,
    ShellResult,
    ShellRunState,
    ShellSessionSnapshot,
    ShellStepState,
    TerminalShell,
)


class FamShellLocalEndToEndTests(unittest.TestCase):
    def test_terminal_to_authenticated_core_gateway_flow(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            os.chmod(root, 0o700)
            path = root / "shell.sock"
            server = UnixShellServer(
                UnixShellServerConfiguration(path),
                PeerAuthorizationPolicy(os.geteuid()),
                ShellRequestDispatcher(WorkflowGateway()),
            )
            server.open()
            self.addCleanup(server.close)
            shell = TerminalShell(
                ShellController(
                    UnixShellCoreClient(UnixShellClientConfiguration(path)),
                    request_id_factory=lambda: "request-e2e",
                ),
                context_id_factory=lambda: "context-e2e",
            )
            added, _ = shell.execute(
                'context add application app:editor "Code editor" editor.observe'
            )
            self.assertIn("context-e2e", added)
            accepted, _ = serve(server, lambda: shell.execute("ask --verify Review code"))
            self.assertIn("State: accepted", accepted)
            waiting, _ = serve(server, lambda: shell.execute("refresh"))
            self.assertIn("Approval required:", waiting)
            terminal, _ = serve(server, lambda: shell.execute("approve"))
            self.assertIn("Result: verified", terminal)
            self.assertIn("Verified local result", terminal)


class WorkflowGateway:
    def ask(self, command):
        return ShellSessionSnapshot(
            "session-e2e", command.request_id, 0, ShellRunState.ACCEPTED,
            steps=(step(ShellStepState.PENDING),), message="Accepted",
        )

    def snapshot(self, session_id):
        approval = ShellApprovalRequest(
            "approval-e2e", "proposal-e2e", "editor.write",
            "Apply reviewed change", datetime(2026, 7, 18, tzinfo=timezone.utc),
            True,
        )
        return ShellSessionSnapshot(
            session_id, "request-e2e", 1, ShellRunState.WAITING_APPROVAL,
            steps=(step(ShellStepState.ACTIVE),), current_step_id="edit",
            message="Change prepared", approval=approval,
        )

    def decide(self, command):
        result = ShellResult(
            "request-e2e", ResultStatus.VERIFIED, "Verified local result",
            verified=True, evidence_ids=("evidence-e2e",),
        )
        return ShellSessionSnapshot(
            command.session_id, "request-e2e", 2, ShellRunState.TERMINAL,
            steps=(step(ShellStepState.SUCCEEDED),), current_step_id="edit",
            message="Complete", result=result,
        )

    def cancel(self, command):
        raise AssertionError("cancel is not expected")


def step(state):
    return ShellPlanStep("edit", "execute_action", "Apply editor change", state)


def serve(server, operation):
    thread = threading.Thread(target=server.serve_once, daemon=True)
    thread.start()
    try:
        return operation()
    finally:
        thread.join(timeout=2)
        if thread.is_alive():
            raise AssertionError("shell server did not finish")


if __name__ == "__main__":
    unittest.main()
