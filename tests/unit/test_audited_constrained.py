import unittest
from datetime import datetime, timezone

from fam_os.supervisor import (
    AuditEmissionError,
    AuditedConstrainedServiceLifecycle,
    AuditedOwnedServiceLifecycle,
    ConstrainedServiceLifecycle,
    CountCeiling,
    CpuQuotaCeiling,
    GENESIS_AUDIT_DIGEST,
    InMemoryServiceOwnershipRegistry,
    OwnedServiceLifecycle,
    ResourceCeiling,
    ResourceLimits,
    ResourceSnapshot,
    ServiceDefinition,
    ServiceState,
    ServiceStatus,
    SupervisorAuditEmitter,
    SupervisorAuditOperation,
    SupervisorAuditOutcome,
    SupervisorAuthorizationError,
    SupervisorCallContext,
    SupervisorCapability,
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


class FakeLifecycle:
    def __init__(self) -> None:
        self.state = ServiceState.INACTIVE
        self.starts = 0
        self.stops = 0

    def start(self, definition):
        self.starts += 1
        self.state = ServiceState.ACTIVE
        return self.status(definition.service_id)

    def stop(self, service_id):
        self.stops += 1
        self.state = ServiceState.INACTIVE
        return self.status(service_id)

    def status(self, service_id):
        return ServiceStatus(service_id, self.state)


class Authorizer:
    def __init__(self, deny_limits=False) -> None:
        self.deny_limits = deny_limits

    def require(self, context, capability, service_id):
        if self.deny_limits and capability is SupervisorCapability.APPLY_SERVICE_RESOURCE_LIMITS:
            raise SupervisorAuthorizationError("limits denied")


class Observer:
    def __init__(self, memory=64) -> None:
        self.memory = memory

    def observe(self, service_id):
        return ResourceSnapshot(
            service_id, memory_limit=ResourceCeiling(self.memory),
            swap_limit=ResourceCeiling(0), cpu_quota=CpuQuotaCeiling(25.0),
            tasks_limit=CountCeiling(8),
        )


def definition():
    return ServiceDefinition(
        "fam-audit-limits", ("/usr/bin/true",),
        limits=ResourceLimits(64, 0, 25.0, 8),
    )


def context():
    return SupervisorCallContext("request-1", "principal-1", "session-1", "authority-1")


def use_case(sink, lifecycle, observer=None, authorizer=None):
    emitter = SupervisorAuditEmitter(
        sink, clock=lambda: NOW,
        event_id_factory=lambda: f"event-{len(sink.records) + 1}",
    )
    owned = OwnedServiceLifecycle(
        lifecycle, authorizer or Authorizer(), InMemoryServiceOwnershipRegistry()
    )
    audited_owned = AuditedOwnedServiceLifecycle(owned, emitter)
    constrained = ConstrainedServiceLifecycle(audited_owned, observer or Observer())
    return AuditedConstrainedServiceLifecycle(constrained, emitter)


class AuditedConstrainedServiceTests(unittest.TestCase):
    def test_verified_start_links_limit_and_service_events(self) -> None:
        sink = SequenceSink()
        outcome = use_case(sink, FakeLifecycle()).start(context(), definition())
        self.assertTrue(outcome.constrained)
        self.assertEqual(
            [
                (SupervisorAuditOperation.APPLY_RESOURCE_LIMITS, SupervisorAuditOutcome.REQUESTED),
                (SupervisorAuditOperation.SERVICE_START, SupervisorAuditOutcome.REQUESTED),
                (SupervisorAuditOperation.SERVICE_START, SupervisorAuditOutcome.SUCCEEDED),
                (SupervisorAuditOperation.APPLY_RESOURCE_LIMITS, SupervisorAuditOutcome.SUCCEEDED),
            ],
            [(record.intent.operation, record.intent.outcome) for record in sink.records],
        )
        limit_operation_ids = {
            sink.records[index].intent.operation_id for index in (0, 3)
        }
        start_operation_ids = {
            sink.records[index].intent.operation_id for index in (1, 2)
        }
        self.assertEqual(1, len(limit_operation_ids))
        self.assertEqual(1, len(start_operation_ids))
        self.assertNotEqual(limit_operation_ids, start_operation_ids)

    def test_mismatch_is_recorded_as_compensated(self) -> None:
        sink = SequenceSink()
        lifecycle = FakeLifecycle()
        outcome = use_case(sink, lifecycle, Observer(memory=128)).start(
            context(), definition()
        )
        self.assertFalse(outcome.constrained)
        self.assertEqual(ServiceState.INACTIVE, lifecycle.state)
        self.assertEqual(SupervisorAuditOutcome.COMPENSATED, sink.records[-1].intent.outcome)
        self.assertEqual("limits.verification_failed", sink.records[-1].intent.reason_code)

    def test_missing_limit_outcome_audit_stops_verified_service(self) -> None:
        lifecycle = FakeLifecycle()
        with self.assertRaises(AuditEmissionError):
            use_case(SequenceSink(fail_on=4), lifecycle).start(context(), definition())
        self.assertEqual(ServiceState.INACTIVE, lifecycle.state)
        self.assertEqual(1, lifecycle.stops)

    def test_missing_request_audit_prevents_any_start(self) -> None:
        lifecycle = FakeLifecycle()
        with self.assertRaises(AuditEmissionError):
            use_case(SequenceSink(fail_on=1), lifecycle).start(context(), definition())
        self.assertEqual(0, lifecycle.starts)


if __name__ == "__main__":
    unittest.main()
