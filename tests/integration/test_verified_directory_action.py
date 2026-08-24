import tempfile
import time
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from fam_os.adapters.shell import UnixShellClientConfiguration, UnixShellCoreClient
from fam_os.core.contracts import ResultKind, ResultStatus
from fam_os.product.service import LocalProductService, ProductServiceSettings
from fam_os.product.restart_recovery import PersistedActionState
from fam_os.shell import (
    ShellAskCommand, ShellContext, ShellContextKind, ShellDecision,
    ShellDecisionCommand,
)
from tests.integration.product_runtime_fixture import ResidentRuntimeFixture


class _NoModelRuntime(ResidentRuntimeFixture):
    def __init__(self):
        super().__init__()
        self.calls = 0

    def chat(self, _request):
        self.calls += 1
        raise AssertionError("directory actions must never invoke a model")

class VerifiedDirectoryActionTests(unittest.TestCase):
    def test_restart_while_awaiting_approval_requires_and_accepts_fresh_decision(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home = root / "home"
            home.mkdir()
            target = home / "Restarted"
            runtime = _NoModelRuntime()
            settings = ProductServiceSettings(
                root / "state", root / "runtime", console_port=0,
            )
            with patch.dict("os.environ", {"HOME": str(home)}):
                first = LocalProductService(settings, runtime)
                first.start()
            client = UnixShellCoreClient(UnixShellClientConfiguration(
                root / "runtime/shell.sock", 5,
            ))
            accepted = client.ask(ShellAskCommand(
                "restart-awaiting", f"Create directory {target}",
                memory_session_id="restart-session",
            ))
            pending = _approval(client, accepted.session_id)
            first.stop()

            with patch.dict("os.environ", {"HOME": str(home)}):
                second = LocalProductService(settings, runtime)
                second.start()
            try:
                client = UnixShellCoreClient(UnixShellClientConfiguration(
                    root / "runtime/shell.sock", 5,
                ))
                recovered = _approval(client, accepted.session_id)
                self.assertEqual(pending.approval.proposal_id, recovered.approval.proposal_id)
                client.decide(_approve(recovered))
                result = _terminal(client, accepted.session_id)
                self.assertEqual(
                    ResultStatus.VERIFIED, result.result.status, result.result,
                )
                self.assertTrue(target.is_dir())
                self.assertEqual(0, runtime.calls)
            finally:
                second.stop()

    def test_restart_after_approval_discards_old_authority_before_execution(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home = root / "home"
            home.mkdir()
            target = home / "FreshApproval"
            runtime = _NoModelRuntime()
            settings = ProductServiceSettings(
                root / "state", root / "runtime", console_port=0,
            )
            with patch.dict("os.environ", {"HOME": str(home)}):
                first = LocalProductService(settings, runtime)
                first.start()
            client = UnixShellCoreClient(UnixShellClientConfiguration(
                root / "runtime/shell.sock", 5,
            ))
            accepted = client.ask(ShellAskCommand(
                "restart-approved", f"Create directory {target}",
                memory_session_id="restart-session",
            ))
            pending = _approval(client, accepted.session_id)
            first.shell_server.dispatcher.gateway._application_gateway.decide(
                _approve(pending),
            )
            self.assertFalse(target.exists())
            first.stop()

            with patch.dict("os.environ", {"HOME": str(home)}):
                second = LocalProductService(settings, runtime)
                second.start()
            try:
                client = UnixShellCoreClient(UnixShellClientConfiguration(
                    root / "runtime/shell.sock", 5,
                ))
                recovered = _approval(client, accepted.session_id)
                self.assertIn("FreshApproval", recovered.approval.summary)
                client.decide(_approve(recovered))
                result = _terminal(client, accepted.session_id)
                repositories = second._storage_unit.core.repositories()
                application = repositories.application_executions.get(
                    accepted.session_id,
                )
                action = repositories.actions.get(
                    f"action-{application.proposal.proposal_id}",
                )
                plan = repositories.plans.get(accepted.session_id)
                self.assertEqual(
                    ResultStatus.VERIFIED, result.result.status,
                    (result.result, action, application, plan.events[-2:]),
                )
                self.assertTrue(target.is_dir())
                self.assertTrue(
                    application.confirmation.confirmation_id.startswith(
                        "confirmation-recovery-",
                    )
                )
                self.assertEqual(0, runtime.calls)
            finally:
                second.stop()

    def test_restart_during_invocation_reobserves_without_provider_retry(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home = root / "home"
            home.mkdir()
            target = home / "ObservedAfterCrash"
            runtime = _NoModelRuntime()
            settings = ProductServiceSettings(
                root / "state", root / "runtime", console_port=0,
            )
            with patch.dict("os.environ", {"HOME": str(home)}):
                first = LocalProductService(settings, runtime)
                first.start()
            client = UnixShellCoreClient(UnixShellClientConfiguration(
                root / "runtime/shell.sock", 5,
            ))
            accepted = client.ask(ShellAskCommand(
                "restart-invoking", f"Create directory {target}",
                memory_session_id="restart-session",
            ))
            pending = _approval(client, accepted.session_id)
            first.shell_server.dispatcher.gateway._application_gateway.decide(
                _approve(pending),
            )
            repositories = first._storage_unit.core.repositories()
            application = repositories.application_executions.get(accepted.session_id)
            action_id = f"action-{application.proposal.proposal_id}"
            action = repositories.actions.get(action_id)
            self.assertTrue(repositories.actions.replace(
                action.state, replace(action, state=PersistedActionState.INVOKING),
            ))
            target.mkdir(mode=0o700)
            first.stop()

            with patch.dict("os.environ", {"HOME": str(home)}):
                second = LocalProductService(settings, runtime)
                second.start()
            try:
                client = UnixShellCoreClient(UnixShellClientConfiguration(
                    root / "runtime/shell.sock", 5,
                ))
                result = _terminal(client, accepted.session_id)
                self.assertEqual(ResultStatus.VERIFIED, result.result.status)
                self.assertTrue(target.is_dir())
                repositories = second._storage_unit.core.repositories()
                action = repositories.actions.get(action_id)
                self.assertEqual(PersistedActionState.VERIFIED, action.state)
                self.assertIsNotNone(action.result.reversal_token)
                self.assertEqual(0, runtime.calls)
            finally:
                second.stop()

    def test_recovered_approval_can_be_denied_without_mutation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home = root / "home"
            home.mkdir()
            target = home / "DeniedAfterRestart"
            runtime = _NoModelRuntime()
            settings = ProductServiceSettings(
                root / "state", root / "runtime", console_port=0,
            )
            with patch.dict("os.environ", {"HOME": str(home)}):
                first = LocalProductService(settings, runtime)
                first.start()
            client = UnixShellCoreClient(UnixShellClientConfiguration(
                root / "runtime/shell.sock", 5,
            ))
            accepted = client.ask(ShellAskCommand(
                "restart-denied", f"Create directory {target}",
                memory_session_id="restart-session",
            ))
            pending = _approval(client, accepted.session_id)
            first.shell_server.dispatcher.gateway._application_gateway.decide(
                _approve(pending),
            )
            first.stop()

            with patch.dict("os.environ", {"HOME": str(home)}):
                second = LocalProductService(settings, runtime)
                second.start()
            try:
                client = UnixShellCoreClient(UnixShellClientConfiguration(
                    root / "runtime/shell.sock", 5,
                ))
                recovered = _approval(client, accepted.session_id)
                client.decide(ShellDecisionCommand(
                    recovered.session_id, recovered.revision,
                    recovered.approval.approval_id, ShellDecision.DENY,
                ))
                result = _terminal(client, accepted.session_id)
                self.assertEqual(ResultStatus.WITHHELD, result.result.status)
                self.assertFalse(target.exists())
                self.assertEqual(0, runtime.calls)
            finally:
                second.stop()

    def test_create_approve_verify_receipt_and_safe_reversal(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home = root / "home"
            home.mkdir()
            target = home / "Desktop" / "Ivan"
            target.parent.mkdir()
            runtime = _NoModelRuntime()
            with patch.dict("os.environ", {"HOME": str(home)}):
                service = LocalProductService(ProductServiceSettings(
                    root / "state", root / "runtime", console_port=0,
                ), runtime)
                service.start()
            try:
                client = UnixShellCoreClient(UnixShellClientConfiguration(
                    root / "runtime/shell.sock", 5,
                ))
                accepted = client.ask(ShellAskCommand(
                    "directory-create", f"Create directory {target}",
                    memory_session_id="directory-session",
                ))
                approval = _approval(client, accepted.session_id)
                self.assertIn(str(target), approval.approval.summary)
                client.decide(_approve(approval))
                result = _terminal(client, accepted.session_id)

                self.assertEqual(ResultStatus.VERIFIED, result.result.status)
                self.assertEqual(ResultKind.ACTION_RECEIPT, result.result.result_kind)
                self.assertTrue(target.is_dir())
                self.assertEqual(0, runtime.calls)
                audit = (root / "state/audit/application-actions.jsonl").read_text()
                self.assertNotIn(str(target), audit)
                self.assertIn("os.directory.create", audit)

                reversal = service.shell_server.dispatcher.gateway.reversals.start(
                    accepted.session_id, "directory-reversal", result.revision,
                )
                reversal_approval = _approval(client, reversal.session_id)
                client.decide(_approve(reversal_approval))
                reversed_result = _terminal(client, reversal.session_id)
                self.assertEqual(
                    ResultKind.ACTION_RECEIPT,
                    reversed_result.result.result_kind,
                )
                self.assertFalse(target.exists())
                self.assertEqual(0, runtime.calls)
            finally:
                service.stop()

    def test_model_claim_cannot_escape_when_capability_is_unavailable(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home = root / "home"
            home.mkdir()
            runtime = _NoModelRuntime()
            with patch.dict("os.environ", {"HOME": str(home)}):
                service = LocalProductService(ProductServiceSettings(
                    root / "state", root / "runtime", console_port=0,
                ), runtime)
                service.start()
            try:
                client = UnixShellCoreClient(UnixShellClientConfiguration(
                    root / "runtime/shell.sock", 5,
                ))
                result = client.ask(ShellAskCommand(
                    "unsupported-delete", "Delete /tmp/important.txt",
                    memory_session_id="directory-session",
                ))
                self.assertEqual(ResultStatus.WITHHELD, result.result.status)
                self.assertEqual(
                    ResultKind.CAPABILITY_UNAVAILABLE,
                    result.result.result_kind,
                )
                self.assertIn("No action was attempted", result.result.reason)
                self.assertEqual(0, runtime.calls)
            finally:
                service.stop()

    def test_denial_never_mutates_and_is_not_an_action_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home = root / "home"
            home.mkdir()
            target = home / "Denied"
            runtime = _NoModelRuntime()
            with patch.dict("os.environ", {"HOME": str(home)}):
                service = LocalProductService(ProductServiceSettings(
                    root / "state", root / "runtime", console_port=0,
                ), runtime)
                service.start()
            try:
                client = UnixShellCoreClient(UnixShellClientConfiguration(
                    root / "runtime/shell.sock", 5,
                ))
                accepted = client.ask(ShellAskCommand(
                    "directory-denied", f"Create directory {target}",
                    memory_session_id="directory-session",
                ))
                approval = _approval(client, accepted.session_id)
                client.decide(ShellDecisionCommand(
                    approval.session_id, approval.revision,
                    approval.approval.approval_id, ShellDecision.DENY,
                ))
                result = _terminal(client, accepted.session_id)
                self.assertEqual(ResultStatus.WITHHELD, result.result.status)
                self.assertEqual(
                    ResultKind.ACTION_PROPOSAL, result.result.result_kind,
                )
                self.assertFalse(target.exists())
                self.assertEqual(0, runtime.calls)
            finally:
                service.stop()

    def test_missing_parent_is_collected_without_model_inference(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home = root / "home"
            home.mkdir()
            parent = home / "Desktop"
            parent.mkdir()
            runtime = _NoModelRuntime()
            with patch.dict("os.environ", {"HOME": str(home)}):
                service = LocalProductService(ProductServiceSettings(
                    root / "state", root / "runtime", console_port=0,
                ), runtime)
                service.start()
            try:
                client = UnixShellCoreClient(UnixShellClientConfiguration(
                    root / "runtime/shell.sock", 5,
                ))
                proposal = client.ask(ShellAskCommand(
                    "directory-needs-parent",
                    "Create a folder, name it Ivan, no content",
                    memory_session_id="follow-up-session",
                ))
                self.assertEqual(
                    ResultKind.ACTION_PROPOSAL, proposal.result.result_kind,
                )
                accepted = client.ask(ShellAskCommand(
                    "directory-has-parent", str(parent),
                    memory_session_id="follow-up-session",
                ))
                approval = _approval(client, accepted.session_id)
                self.assertIn(str(parent / "Ivan"), approval.approval.summary)
                client.decide(ShellDecisionCommand(
                    approval.session_id, approval.revision,
                    approval.approval.approval_id, ShellDecision.DENY,
                ))
                self.assertFalse((parent / "Ivan").exists())
                self.assertEqual(0, runtime.calls)
            finally:
                service.stop()

    def test_selected_workspace_resolves_named_child_without_model_inference(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home = root / "home"
            workspace = home / "Desktop"
            workspace.mkdir(parents=True)
            runtime = _NoModelRuntime()
            with patch.dict("os.environ", {"HOME": str(home)}):
                service = LocalProductService(ProductServiceSettings(
                    root / "state", root / "runtime", console_port=0,
                ), runtime)
                service.start()
            try:
                client = UnixShellCoreClient(UnixShellClientConfiguration(
                    root / "runtime/shell.sock", 5,
                ))
                workspace_uri = workspace.as_uri() + "/"
                accepted = client.ask(ShellAskCommand(
                    "workspace-directory-create", "Create folder Ivan",
                    (
                        ShellContext(
                            "owner-filesystem", ShellContextKind.APPLICATION,
                            "owner-filesystem", "Local filesystem",
                            ("os.directory.inspect", "os.directory.list"),
                        ),
                        ShellContext(
                            "workspace", ShellContextKind.URI,
                            workspace_uri, "Desktop",
                        ),
                    ),
                    memory_session_id="workspace-session",
                ))
                approval = _approval(client, accepted.session_id)
                self.assertIn(str(workspace / "Ivan"), approval.approval.summary)
                client.decide(_approve(approval))
                result = _terminal(client, accepted.session_id)

                self.assertEqual(ResultStatus.VERIFIED, result.result.status)
                self.assertTrue((workspace / "Ivan").is_dir())
                self.assertEqual(0, runtime.calls)
            finally:
                service.stop()


def _approve(snapshot):
    return ShellDecisionCommand(
        snapshot.session_id, snapshot.revision,
        snapshot.approval.approval_id, ShellDecision.APPROVE,
    )


def _approval(client, session_id):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        snapshot = client.snapshot(session_id)
        if snapshot.approval is not None:
            return snapshot
        if snapshot.result is not None:
            raise AssertionError(f"action failed before approval: {snapshot.result}")
        time.sleep(.01)
    raise AssertionError("directory action did not request approval")


def _terminal(client, session_id):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        snapshot = client.snapshot(session_id)
        if snapshot.result is not None:
            return snapshot
        time.sleep(.01)
    raise AssertionError("directory action did not become terminal")


if __name__ == "__main__":
    unittest.main()
