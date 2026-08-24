import unittest
from datetime import timedelta

from fam_os.supervisor import (
    AuditedNetworkEnforcementController,
    NetworkAttachment,
    NetworkAttachmentKind,
    NetworkEnforcementController,
    NetworkEnforcementLease,
    NetworkEnforcementSpec,
    NetworkUsageSnapshot,
    SupervisorAuditOperation,
    SupervisorAuditOutcome,
    SupervisorCallContext,
    SupervisorCapability,
    SupervisorAuthorizationError,
)
from tests.contract.schema_integration_environment_fixtures import NOW


class Authorizer:
    def __init__(self, allowed=True): self.allowed, self.calls = allowed, []
    def require(self, context, capability, service_id):
        self.calls.append((context, capability, service_id))
        if not self.allowed: raise SupervisorAuthorizationError("denied")


class Adapter:
    def __init__(self, spec):
        self.calls = []
        self.lease = NetworkEnforcementLease(
            spec.enforcement_id, (NetworkAttachment(
                spec.attachment_kinds[0], "/run/netns/" + spec.enforcement_id,
                "http://10.0.0.1:8080",
            ),), spec.destinations,
            spec.maximum_network_bytes, NOW, spec.expires_at, "b" * 64,
        )
        self.live = NetworkUsageSnapshot(
            spec.enforcement_id, spec.destinations, 10, 20,
            spec.maximum_network_bytes, False, False, NOW, "c" * 64,
        )
        self.final = NetworkUsageSnapshot(
            spec.enforcement_id, spec.destinations, 10, 20,
            spec.maximum_network_bytes, False, True, NOW, "d" * 64,
        )
    def open(self, spec): self.calls.append("open"); return self.lease
    def observe(self, identity): self.calls.append("observe"); return self.live
    def close(self, identity): self.calls.append("close"); return self.final
    def recover(self, spec): self.calls.append("recover"); return self.final


class Audit:
    def __init__(self, fail_outcome=None): self.calls, self.fail_outcome = [], fail_outcome
    def new_operation_id(self): return "operation-1"
    def emit(self, context, service_id, operation, outcome, operation_id, **fields):
        self.calls.append((operation, outcome, fields))
        if outcome is self.fail_outcome: raise RuntimeError("audit unavailable")


class SupervisorNetworkEnforcementTests(unittest.TestCase):
    def setUp(self):
        self.spec = NetworkEnforcementSpec(
            "fam-network-environment-1", "environment-1",
            (NetworkAttachmentKind.LINUX_NAMESPACE,), ("registry.example:443",),
            10_000, NOW + timedelta(minutes=5), "a" * 64,
        )
        self.context = SupervisorCallContext(
            "request-1", "fam-core", "session-1", "authority-1",
        )

    def _subject(self, *, allowed=True, audit=None):
        authorizer, adapter = Authorizer(allowed), Adapter(self.spec)
        controller = NetworkEnforcementController(authorizer, adapter)
        return AuditedNetworkEnforcementController(
            controller, audit or Audit(),
        ), authorizer, adapter

    def test_all_operations_are_exactly_authorized_and_audited(self):
        subject, authorizer, adapter = self._subject()
        lease = subject.open(self.context, self.spec, NOW)
        self.assertEqual(adapter.lease, lease)
        self.assertEqual(adapter.live, subject.observe(self.context, lease.enforcement_id))
        self.assertEqual(adapter.final, subject.close(self.context, lease.enforcement_id))
        self.assertEqual(adapter.final, subject.recover(self.context, self.spec))
        self.assertTrue(all(
            call[1] is SupervisorCapability.ENFORCE_ALLOWLISTED_NETWORK
            and call[2] == self.spec.enforcement_id for call in authorizer.calls
        ))

    def test_denial_is_audited_before_adapter_effect(self):
        audit = Audit(); subject, _authorizer, adapter = self._subject(allowed=False, audit=audit)
        with self.assertRaises(SupervisorAuthorizationError):
            subject.open(self.context, self.spec, NOW)
        self.assertEqual([], adapter.calls)
        self.assertEqual(SupervisorAuditOutcome.REQUESTED, audit.calls[0][1])
        self.assertEqual(SupervisorAuditOutcome.DENIED, audit.calls[1][1])

    def test_request_audit_failure_prevents_effect(self):
        audit = Audit(SupervisorAuditOutcome.REQUESTED)
        subject, _authorizer, adapter = self._subject(audit=audit)
        with self.assertRaisesRegex(RuntimeError, "audit unavailable"):
            subject.open(self.context, self.spec, NOW)
        self.assertEqual([], adapter.calls)

    def test_success_audit_failure_compensates_open(self):
        audit = Audit(SupervisorAuditOutcome.SUCCEEDED)
        subject, _authorizer, adapter = self._subject(audit=audit)
        with self.assertRaisesRegex(RuntimeError, "audit unavailable"):
            subject.open(self.context, self.spec, NOW)
        self.assertEqual(["open", "close"], adapter.calls)
        self.assertEqual(SupervisorAuditOperation.NETWORK_OPEN, audit.calls[0][0])

    def test_expired_request_is_denied_before_effect(self):
        subject, _authorizer, adapter = self._subject()
        with self.assertRaisesRegex(PermissionError, "expired"):
            subject.open(self.context, self.spec, self.spec.expires_at)
        self.assertEqual([], adapter.calls)


if __name__ == "__main__":
    unittest.main()
