import unittest
from datetime import datetime, timedelta, timezone

from fam_os.supervisor import (
    AccessApplicationEvidence,
    AccessEvidenceStatus,
    AccessMode,
    AccessResourceDescriptor,
    AccessResourceKind,
    AuditEmissionError,
    AuditedServiceAccessController,
    GENESIS_AUDIT_DIGEST,
    InMemoryAccessGrantRegistry,
    InMemoryAccessResourceCatalog,
    InMemoryServiceOwnershipRegistry,
    OwnedService,
    ServiceAccessController,
    ServiceAccessGrant,
    ServiceDefinition,
    SupervisorAuditEmitter,
    SupervisorAuditOutcome,
    SupervisorAuthorizationError,
    SupervisorCallContext,
)
from fam_os.supervisor.audit_codec import create_audit_record


NOW = datetime(2026, 7, 16, tzinfo=timezone.utc)


class SequenceSink:
    def __init__(self, fail_on=None) -> None:
        self.records = []
        self.fail_on = fail_on

    def append(self, intent):
        if len(self.records) + 1 == self.fail_on:
            raise AuditEmissionError("required audit failed")
        previous = self.records[-1].digest if self.records else GENESIS_AUDIT_DIGEST
        record = create_audit_record(intent, len(self.records) + 1, previous)
        self.records.append(record)
        return record


class AllowAuthorizer:
    def require(self, context, capability, service_id):
        pass


class AccessAdapter:
    def __init__(self) -> None:
        self.calls = []

    def grant(self, grant, resource):
        self.calls.append("grant")
        return _evidence(grant, AccessEvidenceStatus.GRANTED)

    def revoke(self, grant, resource):
        self.calls.append("revoke")
        return _evidence(grant, AccessEvidenceStatus.REVOKED)


def _evidence(grant, status):
    return AccessApplicationEvidence(
        grant.grant_id, grant.service_id, grant.resource_id,
        "fake.audit-access", status, NOW,
    )


def context(principal="principal-1"):
    return SupervisorCallContext("request-1", principal, "session-1", "authority-1")


def grant():
    return ServiceAccessGrant(
        "grant-1", "authority-1", "principal-1", "session-1",
        "fam-audit-test", "filesystem.models", AccessResourceKind.FILESYSTEM,
        AccessMode.READ, NOW - timedelta(minutes=1), NOW + timedelta(hours=1),
    )


def use_case(sink):
    ownership = InMemoryServiceOwnershipRegistry()
    ownership.claim(OwnedService(
        "principal-1", "session-1",
        ServiceDefinition("fam-audit-test", ("/usr/bin/true",)),
    ))
    adapter = AccessAdapter()
    controller = ServiceAccessController(
        AllowAuthorizer(), ownership,
        InMemoryAccessResourceCatalog((AccessResourceDescriptor(
            "filesystem.models", AccessResourceKind.FILESYSTEM, (AccessMode.READ,)
        ),)),
        InMemoryAccessGrantRegistry(), adapter,
    )
    emitter = SupervisorAuditEmitter(
        sink, clock=lambda: NOW,
        event_id_factory=lambda: f"event-{len(sink.records) + 1}",
    )
    return AuditedServiceAccessController(controller, emitter), adapter


class AuditedServiceAccessTests(unittest.TestCase):
    def test_grant_and_revoke_have_linked_audit_outcomes(self) -> None:
        sink = SequenceSink()
        audited, adapter = use_case(sink)
        audited.grant(context(), grant(), NOW)
        audited.revoke(context(), "fam-audit-test", "grant-1", NOW)
        self.assertEqual(["grant", "revoke"], adapter.calls)
        self.assertEqual(
            [SupervisorAuditOutcome.REQUESTED, SupervisorAuditOutcome.SUCCEEDED] * 2,
            [record.intent.outcome for record in sink.records],
        )
        self.assertTrue(all(
            record.intent.resource_id == "filesystem.models"
            for record in sink.records[0:2] + sink.records[3:4]
        ))
        self.assertEqual(
            sink.records[0].intent.operation_id,
            sink.records[1].intent.operation_id,
        )
        self.assertEqual(
            sink.records[2].intent.operation_id,
            sink.records[3].intent.operation_id,
        )
        self.assertNotEqual(
            sink.records[0].intent.operation_id,
            sink.records[2].intent.operation_id,
        )

    def test_request_audit_failure_prevents_adapter_call(self) -> None:
        audited, adapter = use_case(SequenceSink(fail_on=1))
        with self.assertRaises(AuditEmissionError):
            audited.grant(context(), grant(), NOW)
        self.assertEqual([], adapter.calls)

    def test_outcome_audit_failure_revokes_applied_grant(self) -> None:
        sink = SequenceSink(fail_on=2)
        audited, adapter = use_case(sink)
        with self.assertRaises(AuditEmissionError):
            audited.grant(context(), grant(), NOW)
        self.assertEqual(["grant", "revoke"], adapter.calls)
        self.assertTrue(audited.controller.grants.get("grant-1").revoked)

    def test_denied_grant_records_bounded_reason(self) -> None:
        sink = SequenceSink()
        audited, adapter = use_case(sink)
        with self.assertRaises(SupervisorAuthorizationError):
            audited.grant(context("other-principal"), grant(), NOW)
        self.assertEqual([], adapter.calls)
        self.assertEqual(SupervisorAuditOutcome.DENIED, sink.records[-1].intent.outcome)
        self.assertEqual("authorization.denied", sink.records[-1].intent.reason_code)


if __name__ == "__main__":
    unittest.main()
