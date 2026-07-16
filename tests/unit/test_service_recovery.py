import unittest
from datetime import datetime, timedelta, timezone

from fam_os.supervisor import (
    AccessApplicationEvidence,
    AccessEvidenceStatus,
    AccessMode,
    AccessResourceDescriptor,
    AccessResourceKind,
    AuditEmissionError,
    AuditedOwnedServiceLifecycle,
    AuditedServiceAccessController,
    GENESIS_AUDIT_DIGEST,
    InMemoryAccessGrantRegistry,
    InMemoryAccessResourceCatalog,
    InMemoryServiceOwnershipRegistry,
    OwnedService,
    OwnedServiceLifecycle,
    ResourceSnapshot,
    ServiceAccessController,
    ServiceAccessGrant,
    ServiceDefinition,
    ServiceRecoveryController,
    ServiceRecoveryError,
    ServiceState,
    ServiceStatus,
    ServiceTerminationDisposition,
    ServiceTerminationReason,
    SupervisorAuditEmitter,
    SupervisorAuditOperation,
    SupervisorAuditOutcome,
    SupervisorAuthorizationError,
    SupervisorCallContext,
    SupervisorCapability,
)
from fam_os.supervisor.audit_codec import create_audit_record


NOW = datetime(2026, 7, 16, 15, tzinfo=timezone.utc)
SERVICE_ID = "fam-recovery-test"


class SequenceSink:
    def __init__(self, fail_on=None):
        self.records = []
        self.fail_on = fail_on

    def append(self, intent):
        if len(self.records) + 1 == self.fail_on:
            raise AuditEmissionError("required audit failed")
        previous = self.records[-1].digest if self.records else GENESIS_AUDIT_DIGEST
        record = create_audit_record(intent, len(self.records) + 1, previous)
        self.records.append(record)
        return record


class Lifecycle:
    def __init__(self, state, stop_state=ServiceState.INACTIVE):
        self.state = state
        self.stop_state = stop_state
        self.stops = 0
        self.status_calls = 0
        self.resets = 0

    def start(self, definition):
        self.state = ServiceState.ACTIVE
        return self.status(definition.service_id)

    def stop(self, service_id):
        self.stops += 1
        self.state = self.stop_state
        return ServiceStatus(service_id, self.state)

    def status(self, service_id):
        self.status_calls += 1
        pid = 123 if self.state is ServiceState.ACTIVE else None
        return ServiceStatus(service_id, self.state, main_pid=pid)

    def reset_failed(self, service_id):
        self.resets += 1
        self.state = ServiceState.INACTIVE
        return ServiceStatus(service_id, self.state)


class Authorizer:
    def __init__(self, denied=()):
        self.denied = set(denied)

    def require(self, context, capability, service_id):
        if capability in self.denied:
            raise SupervisorAuthorizationError("denied")


class Observer:
    def __init__(self, service_id=SERVICE_ID):
        self.service_id = service_id

    def observe(self, service_id):
        return ResourceSnapshot(self.service_id, memory_current_bytes=64)


class AccessAdapter:
    def __init__(self):
        self.revoked = []

    def grant(self, grant, resource):
        return _access_evidence(grant, AccessEvidenceStatus.GRANTED)

    def revoke(self, grant, resource):
        self.revoked.append(grant.grant_id)
        return _access_evidence(grant, AccessEvidenceStatus.REVOKED)


def _access_evidence(grant, status):
    return AccessApplicationEvidence(
        grant.grant_id, grant.service_id, grant.resource_id,
        "fake.recovery", status, NOW,
    )


def context():
    return SupervisorCallContext(
        "request-1", "principal-1", "session-1", "authority-1"
    )


def grant(grant_id="grant-1", service_id=SERVICE_ID):
    return ServiceAccessGrant(
        grant_id, "authority-1", "principal-1", "session-1", service_id,
        "filesystem.models", AccessResourceKind.FILESYSTEM, AccessMode.READ,
        NOW - timedelta(minutes=1), NOW + timedelta(hours=1),
    )


def use_case(state, *, sink=None, denied=(), stop_state=ServiceState.INACTIVE):
    sink = sink or SequenceSink()
    adapter = Lifecycle(state, stop_state)
    authorizer = Authorizer(denied)
    ownership = InMemoryServiceOwnershipRegistry()
    ownership.claim(OwnedService(
        "principal-1", "session-1",
        ServiceDefinition(SERVICE_ID, ("/usr/bin/true",)),
    ))
    owned = OwnedServiceLifecycle(adapter, authorizer, ownership)
    emitter = SupervisorAuditEmitter(
        sink, clock=lambda: NOW,
        event_id_factory=lambda: f"event-{len(sink.records) + 1}",
        operation_id_factory=lambda: f"operation-{len(sink.records) + 1}",
    )
    grants = InMemoryAccessGrantRegistry()
    access_adapter = AccessAdapter()
    controller = ServiceAccessController(
        authorizer, ownership,
        InMemoryAccessResourceCatalog((AccessResourceDescriptor(
            "filesystem.models", AccessResourceKind.FILESYSTEM,
            (AccessMode.READ,),
        ),)),
        grants, access_adapter,
    )
    audited_access = AuditedServiceAccessController(controller, emitter)
    recovery = ServiceRecoveryController(
        AuditedOwnedServiceLifecycle(owned, emitter), audited_access,
        Observer(), adapter, emitter, clock=lambda: NOW,
    )
    return recovery, adapter, grants, access_adapter, sink


class ServiceRecoveryTests(unittest.TestCase):
    def test_terminates_active_service_and_revokes_sorted_grants(self):
        recovery, lifecycle, grants, access, sink = use_case(ServiceState.ACTIVE)
        grants.record(grant("grant-2"))
        grants.record(grant("grant-1"))

        report = recovery.terminate(
            context(), SERVICE_ID, ServiceTerminationReason.USER_REQUESTED
        )

        self.assertEqual(ServiceTerminationDisposition.TERMINATED, report.disposition)
        self.assertEqual(("grant-1", "grant-2"), report.revoked_grant_ids)
        self.assertEqual(["grant-1", "grant-2"], access.revoked)
        self.assertEqual((1, ServiceState.INACTIVE), (lifecycle.stops, lifecycle.state))
        self.assertEqual(SupervisorAuditOperation.TERMINATE_SERVICE, sink.records[0].intent.operation)
        self.assertEqual(SupervisorAuditOutcome.SUCCEEDED, sink.records[-1].intent.outcome)
        self.assertEqual(sink.records[0].intent.operation_id, sink.records[-1].intent.operation_id)

    def test_recovers_only_failed_service_to_inactive(self):
        recovery, lifecycle, _, _, sink = use_case(ServiceState.FAILED)

        report = recovery.recover_failed(context(), SERVICE_ID)

        self.assertEqual(
            ServiceTerminationDisposition.RECOVERED_TO_INACTIVE,
            report.disposition,
        )
        self.assertEqual(1, lifecycle.stops)
        self.assertEqual(1, lifecycle.resets)
        self.assertEqual(SupervisorAuditOperation.RECOVER_SERVICE, sink.records[0].intent.operation)
        self.assertEqual("recovery.inactive", sink.records[-1].intent.evidence_ref)

    def test_recovery_rejects_nonfailed_service_without_stop(self):
        recovery, lifecycle, _, _, sink = use_case(ServiceState.ACTIVE)

        with self.assertRaises(ServiceRecoveryError):
            recovery.recover_failed(context(), SERVICE_ID)

        self.assertEqual(0, lifecycle.stops)
        self.assertEqual("recovery.incomplete", sink.records[-1].intent.reason_code)

    def test_unknown_or_nonterminal_final_state_fails_closed(self):
        unknown, lifecycle, _, _, _ = use_case(ServiceState.UNKNOWN)
        with self.assertRaises(ServiceRecoveryError):
            unknown.terminate(
                context(), SERVICE_ID, ServiceTerminationReason.USER_REQUESTED
            )
        self.assertEqual(0, lifecycle.stops)

        active, lifecycle, _, _, _ = use_case(
            ServiceState.ACTIVE, stop_state=ServiceState.ACTIVE
        )
        with self.assertRaises(ServiceRecoveryError):
            active.terminate(
                context(), SERVICE_ID, ServiceTerminationReason.USER_REQUESTED
            )
        self.assertEqual(1, lifecycle.stops)

    def test_request_audit_failure_prevents_status_and_stop(self):
        sink = SequenceSink(fail_on=1)
        recovery, lifecycle, _, _, _ = use_case(ServiceState.ACTIVE, sink=sink)

        with self.assertRaises(AuditEmissionError):
            recovery.terminate(
                context(), SERVICE_ID, ServiceTerminationReason.USER_REQUESTED
            )

        self.assertEqual((0, 0), (lifecycle.status_calls, lifecycle.stops))

    def test_denied_termination_is_audited_before_adapter_access(self):
        recovery, lifecycle, _, _, sink = use_case(
            ServiceState.ACTIVE,
            denied=(SupervisorCapability.SAFE_TERMINATE_OWNED_SERVICE,),
        )

        with self.assertRaises(SupervisorAuthorizationError):
            recovery.terminate(
                context(), SERVICE_ID, ServiceTerminationReason.USER_REQUESTED
            )

        self.assertEqual(0, lifecycle.status_calls)
        self.assertEqual(SupervisorAuditOutcome.DENIED, sink.records[-1].intent.outcome)

    def test_outcome_audit_failure_does_not_restart_terminated_service(self):
        sink = SequenceSink(fail_on=2)
        recovery, lifecycle, _, _, _ = use_case(ServiceState.ACTIVE, sink=sink)

        with self.assertRaises(AuditEmissionError):
            recovery.terminate(
                context(), SERVICE_ID, ServiceTerminationReason.USER_REQUESTED
            )

        self.assertEqual(ServiceState.INACTIVE, lifecycle.state)
        self.assertEqual(1, lifecycle.stops)

    def test_registry_returns_only_unrevoked_service_grants_sorted(self):
        registry = InMemoryAccessGrantRegistry()
        registry.record(grant("grant-2"))
        registry.record(grant("grant-1"))
        registry.record(grant("grant-other", "fam-other"))
        registry.revoke("grant-2", NOW)

        matches = registry.unrevoked_for_service(SERVICE_ID)

        self.assertEqual(("grant-1",), tuple(item.grant.grant_id for item in matches))


if __name__ == "__main__":
    unittest.main()
