import unittest
from dataclasses import replace

from fam_os.core.engineering import (
    CandidateWorkspace,
    EngineeringAuthorizationDecision,
    EngineeringAuthority,
    IntegrationEnvironmentService,
    IntegrationNetworkMode,
    IntegrationNetworkUsage,
)
from tests.contract.schema_integration_environment_fixtures import (
    NOW,
    integration_environment_schema_values,
)


class RecordingAuthorizer:
    def __init__(self, allowed=True):
        self.allowed = allowed
        self.requests = []

    def authorize(self, request):
        self.requests.append(request)
        return EngineeringAuthorizationDecision(
            f"decision-{len(self.requests)}", request.request_id,
            request.grant_id, request.authority, NOW, self.allowed,
            "authorized" if self.allowed else "revoked",
        )


class RecordingExecutor:
    def __init__(self, receipt):
        self.receipt = receipt
        self.launch_call = None
        self.cleanup_call = None

    def launch(self, plan, root, permit, control):
        self.launch_call = (plan, root, permit)
        if not control.authorization_active():
            raise PermissionError("live authority disappeared")
        return self.receipt

    def cleanup(self, plan, receipt, root, permit):
        self.cleanup_call = (plan, receipt, root, permit)
        return self.receipt


class NetworkSigner:
    key_id = "device-key-1"
    def sign(self, request): return request


class IntegrationEnvironmentServiceTests(unittest.TestCase):
    def setUp(self):
        _service, self.plan, self.permit, self.receipt, _result = (
            integration_environment_schema_values()
        )
        self.candidate = CandidateWorkspace(
            self.plan.candidate_id, self.plan.task_id, "baseline-1",
            "/owner/workspace", self.plan.candidate_root, NOW,
            "copy", "a" * 64, (),
        )

    def test_exact_execute_authority_mints_permit_and_rechecks_live(self):
        authorizer = RecordingAuthorizer()
        executor = RecordingExecutor(self.receipt)
        identifiers = iter(("request-1", "environment-permit-1"))
        service = IntegrationEnvironmentService(
            authorizer, executor, lambda: NOW, lambda: next(identifiers),
        )
        observed = []
        def observe_permit(permit):
            self.assertIsNone(executor.launch_call)
            observed.append(permit)
        result = service.start(
            self.plan, self.candidate, "grant-1", "fam-core", "session-1",
            lambda: False, observe_permit,
        )
        self.assertEqual("execute", authorizer.requests[0].authority.value)
        self.assertEqual("integration-environment", authorizer.requests[0].toolchain)
        self.assertEqual(
            self.candidate.owner_workspace,
            authorizer.requests[0].workspace_root,
        )
        self.assertEqual("environment-permit-1", executor.launch_call[2].permit_id)
        self.assertEqual(executor.launch_call[2], result.permit)
        self.assertEqual((result.permit,), tuple(observed))
        self.assertEqual(self.receipt, result.receipt)
        self.assertEqual(2, len(authorizer.requests))

    def test_denial_and_candidate_mismatch_have_no_executor_effect(self):
        authorizer = RecordingAuthorizer(False)
        executor = RecordingExecutor(self.receipt)
        service = IntegrationEnvironmentService(authorizer, executor, lambda: NOW)
        with self.assertRaisesRegex(PermissionError, "exact live authority"):
            service.start(
                self.plan, self.candidate, "grant-1", "fam-core", "session-1",
                lambda: False,
            )
        self.assertIsNone(executor.launch_call)
        with self.assertRaisesRegex(ValueError, "does not match"):
            service.start(
                self.plan, self.candidate.__class__(
                    "other", self.candidate.task_id, self.candidate.baseline_id,
                    self.candidate.owner_workspace, self.candidate.candidate_workspace,
                    NOW, "copy", "a" * 64, (),
                ),
                "grant-1", "fam-core", "session-1", lambda: False,
            )

    def test_cleanup_requires_exact_original_identities_without_live_authority(self):
        executor = RecordingExecutor(self.receipt)
        service = IntegrationEnvironmentService(
            RecordingAuthorizer(), executor, lambda: NOW,
        )
        service.cleanup(self.plan, self.candidate, self.receipt, self.permit)
        self.assertIsNotNone(executor.cleanup_call)
        with self.assertRaisesRegex(PermissionError, "identities"):
            service.cleanup(
                self.plan, self.candidate, self.receipt,
                self.permit.__class__(
                    "other", self.permit.environment_id,
                    self.permit.approved_changeset_id, self.permit.exact_host_id,
                    self.permit.authorization_decision_ids,
                    self.permit.issued_at, self.permit.expires_at,
                ),
            )

    def test_expiry_and_precancel_fail_before_authorization(self):
        authorizer = RecordingAuthorizer()
        executor = RecordingExecutor(self.receipt)
        service = IntegrationEnvironmentService(
            authorizer, executor, lambda: self.plan.expires_at,
        )
        with self.assertRaisesRegex(PermissionError, "not active"):
            service.start(
                self.plan, self.candidate, "grant-1", "fam-core", "session-1",
                lambda: False,
            )
        service = IntegrationEnvironmentService(authorizer, executor, lambda: NOW)
        with self.assertRaisesRegex(PermissionError, "cancelled"):
            service.start(
                self.plan, self.candidate, "grant-1", "fam-core", "session-1",
                lambda: True,
            )
        self.assertEqual([], authorizer.requests)
        self.assertIsNone(executor.launch_call)

    def test_allowlisted_receipt_requires_exact_broker_accounting(self):
        plan = replace(
            self.plan, network_mode=IntegrationNetworkMode.ALLOWLIST,
            network_hosts=("registry.example:443",),
            required_authorities=(
                EngineeringAuthority.EXECUTE, EngineeringAuthority.NETWORK,
            ),
        )
        service = IntegrationEnvironmentService(
            RecordingAuthorizer(), RecordingExecutor(self.receipt),
            lambda: NOW,
            iter(("request-exec", "request-network", "environment-permit-1")).__next__,
        )
        with self.assertRaisesRegex(PermissionError, "signing is unavailable"):
            service.start(
                plan, self.candidate, "grant-1", "fam-core", "session-1",
                lambda: False,
            )
        service = IntegrationEnvironmentService(
            RecordingAuthorizer(), RecordingExecutor(self.receipt),
            lambda: NOW,
            iter(("request-exec", "request-network", "environment-permit-1")).__next__,
            NetworkSigner(),
        )
        with self.assertRaisesRegex(ValueError, "requires network usage"):
            service.start(
                plan, self.candidate, "grant-1", "fam-core", "session-1",
                lambda: False,
            )
        usage = IntegrationNetworkUsage(
            "broker-1", plan.environment_id, plan.network_hosts,
            10, 20, plan.resource_impact.max_network_bytes,
            False, False, NOW, "d" * 64,
        )
        receipt = replace(self.receipt, network_usage=usage)
        identifiers = iter((
            "request-exec", "request-network", "environment-permit-1",
        ))
        result = IntegrationEnvironmentService(
            RecordingAuthorizer(), RecordingExecutor(receipt),
            lambda: NOW, lambda: next(identifiers), NetworkSigner(),
        ).start(
            plan, self.candidate, "grant-1", "fam-core", "session-1",
            lambda: False,
        )
        self.assertEqual(usage, result.receipt.network_usage)
        self.assertIsNotNone(result.permit.network_request)
        self.assertEqual(
            ("registry.example:443",), result.permit.network_request.destinations,
        )
        with self.assertRaisesRegex(ValueError, "finalized"):
            IntegrationEnvironmentService(
                RecordingAuthorizer(), RecordingExecutor(receipt), lambda: NOW,
            ).cleanup(plan, self.candidate, receipt, self.permit)


if __name__ == "__main__":
    unittest.main()
