import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from fam_os.adapters.shell import UnixShellClientConfiguration, UnixShellCoreClient
from fam_os.core.contracts import ResultAssurance
from fam_os.product.service import LocalProductService, ProductServiceSettings
from fam_os.product.restart_recovery import PersistedActionState
from fam_os.product.storage.terminal_redaction import TERMINAL_CONTENT_REDACTION
from fam_os.schemas import dumps_document
from fam_os.shell import ShellCancelCommand, ShellDecision, ShellDecisionCommand
from tests.integration.product_action_fixture import (
    AFTER,
    ActionConnector,
    CountingRuntime,
    approval,
    command,
    terminal,
)
from tests.integration.product_runtime_fixture import ContextProfileFixture


class ProductApplicationActionTests(unittest.TestCase):
    def test_inconclusive_restart_action_is_blocked_without_provider_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            settings = ProductServiceSettings(
                root / "state", root / "runtime", console_port=0,
            )
            first = LocalProductService(
                settings, CountingRuntime(),
                context_profile_observer=ContextProfileFixture(),
            )
            first.start()
            connector = ActionConnector(root / "runtime/applications.sock")
            connector.start()
            self.assertTrue(connector.registered.wait(2))
            client = _client(root)
            accepted = client.ask(command())
            pending = approval(client, accepted.session_id)
            first.shell_server.dispatcher.gateway._application_gateway.decide(
                ShellDecisionCommand(
                    pending.session_id, pending.revision,
                    pending.approval.approval_id, ShellDecision.APPROVE,
                ),
            )
            repositories = first._storage_unit.core.repositories()
            action = repositories.actions.get("action-proposal-live")
            self.assertTrue(repositories.actions.replace(
                action.state, replace(action, state=PersistedActionState.INVOKING),
            ))
            connector.close()
            first.stop()

            second = LocalProductService(
                settings, CountingRuntime(),
                context_profile_observer=ContextProfileFixture(),
            )
            second.start()
            try:
                client = _client(root)
                blocked = client.snapshot(accepted.session_id)
                self.assertIsNone(blocked.result)
                self.assertIsNone(blocked.approval)
                self.assertIn("uncertain", blocked.message.lower())
                self.assertEqual(
                    (), second.shell_server.dispatcher.gateway._workers.active_ids(),
                )
                repositories = second._storage_unit.core.repositories()
                action = repositories.actions.get("action-proposal-live")
                application = repositories.application_executions.get(
                    accepted.session_id,
                )
                self.assertEqual(
                    PersistedActionState.RECONCILIATION_REQUIRED, action.state,
                )
                self.assertEqual("recovery_required", application.state.value)
            finally:
                second.stop()

    def test_preview_approval_action_and_postconditions_are_production_wired(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            service = LocalProductService(ProductServiceSettings(
                root / "state", root / "runtime", console_port=0,
            ), CountingRuntime(), context_profile_observer=ContextProfileFixture())
            service.start()
            connector = ActionConnector(root / "runtime/applications.sock")
            connector.start()
            try:
                self.assertTrue(connector.registered.wait(2))
                client = _client(root)
                accepted = client.ask(command())
                pending = approval(client, accepted.session_id)
                self.assertEqual(0, json.loads(pending.approval.summary)["edits"])
                running = _approve(client, pending)
                self.assertIsNone(running.result)
                result = terminal(client, accepted.session_id)
                self.assertTrue(result.result.verified)
                self.assertEqual(ResultAssurance.VERIFIED, result.result.assurance)
                self.assertTrue(connector.executed.wait(1))
                repositories = service._storage_unit.core.repositories()
                action = repositories.actions.get(
                    "action-proposal-live",
                )
                self.assertEqual("verified", action.state.value)
                application = repositories.application_executions.get(
                    accepted.session_id,
                )
                request = repositories.requests.get("action-request")
                self.assertEqual(TERMINAL_CONTENT_REDACTION, request.prompt)
                self.assertEqual(
                    TERMINAL_CONTENT_REDACTION,
                    application.routed.admitted.request.prompt,
                )
                self.assertEqual(
                    TERMINAL_CONTENT_REDACTION, action.proposal.request.summary,
                )
                learned = service.outcome_learning.records()
                self.assertEqual(1, len(learned))
                encoded = dumps_document(learned[0])
                self.assertNotIn("Apply the requested edit", encoded)
                self.assertNotIn("file:///workspace/main.py", encoded)
            finally:
                connector.close()
                service.stop()

    def test_verified_action_can_be_undone_without_model_generated_token(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = CountingRuntime()
            service = LocalProductService(ProductServiceSettings(
                root / "state", root / "runtime", console_port=0,
            ), runtime, context_profile_observer=ContextProfileFixture())
            service.start()
            connector = ActionConnector(root / "runtime/applications.sock")
            connector.start()
            try:
                self.assertTrue(connector.registered.wait(2))
                client = _client(root)
                accepted = client.ask(command())
                pending = approval(client, accepted.session_id)
                _approve(client, pending)
                applied = terminal(client, accepted.session_id)
                self.assertTrue(applied.result.verified)

                api = service.console_server.task_api
                status = api.reversal(accepted.session_id)
                self.assertTrue(status["available"])
                cancelled = api.reverse(accepted.session_id, {
                    "request_id": "undo-cancelled",
                    "expected_revision": status["expected_revision"],
                })
                cancelled_pending = approval(client, cancelled.session_id)
                in_progress = api.reversal(accepted.session_id)
                self.assertFalse(in_progress["available"])
                self.assertEqual("reversal_in_progress", in_progress["reason_code"])
                with self.assertRaisesRegex(ValueError, "reversal_in_progress"):
                    api.reverse(accepted.session_id, {
                        "request_id": "undo-concurrent",
                        "expected_revision": status["expected_revision"],
                    })
                client.cancel(ShellCancelCommand(
                    cancelled.session_id, cancelled_pending.revision,
                ))
                retryable = api.reversal(accepted.session_id)
                self.assertTrue(retryable["available"])
                undo = api.reverse(accepted.session_id, {
                    "request_id": "undo-request",
                    "expected_revision": retryable["expected_revision"],
                })
                undo_pending = approval(client, undo.session_id)
                _approve(client, undo_pending)
                undone = terminal(client, undo.session_id)

                self.assertTrue(undone.result.verified)
                self.assertIn("reversed", undone.result.content)
                self.assertNotIn("undo-live", undone.result.content)
                self.assertTrue(connector.reversed.wait(1))
                self.assertFalse(connector.mutated)
                self.assertEqual(1, len(runtime.calls))
                undo_preparation = connector.preparations[-1]
                self.assertEqual(
                    "vscode.workspace_edit.undo", undo_preparation.capability_id,
                )
                self.assertEqual(AFTER, undo_preparation.expected_revision)
                self.assertEqual(
                    {"reversal_token": "undo-live"}, undo_preparation.parameters,
                )
                consumed = api.reversal(accepted.session_id)
                self.assertFalse(consumed["available"])
                self.assertEqual("reversal_already_completed", consumed["reason_code"])
            finally:
                connector.close()
                service.stop()

    def test_cancel_at_approval_revokes_authority_without_invoking_action(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            service = LocalProductService(ProductServiceSettings(
                root / "state", root / "runtime", console_port=0,
            ), CountingRuntime(), context_profile_observer=ContextProfileFixture())
            service.start()
            connector = ActionConnector(root / "runtime/applications.sock")
            connector.start()
            try:
                self.assertTrue(connector.registered.wait(2))
                client = _client(root)
                accepted = client.ask(command())
                pending = approval(client, accepted.session_id)
                result = client.cancel(ShellCancelCommand(
                    accepted.session_id, pending.revision,
                ))
                self.assertEqual("withheld", result.result.status.value)
                repositories = service._storage_unit.core.repositories()
                action = repositories.actions.get("action-proposal-live")
                application = repositories.application_executions.get(
                    accepted.session_id,
                )
                grant = repositories.application_permissions.get(
                    application.permission_grant_id,
                )
                self.assertEqual("cancelled", action.state.value)
                self.assertEqual("terminal", application.state.value)
                self.assertIsNotNone(grant.revoked_at)
                self.assertFalse(connector.executed.is_set())
            finally:
                connector.close()
                service.stop()


def _client(root):
    return UnixShellCoreClient(UnixShellClientConfiguration(
        root / "runtime/shell.sock", 5,
    ))


def _approve(client, pending):
    return client.decide(ShellDecisionCommand(
        pending.session_id, pending.revision, pending.approval.approval_id,
        ShellDecision.APPROVE,
    ))


if __name__ == "__main__":
    unittest.main()
