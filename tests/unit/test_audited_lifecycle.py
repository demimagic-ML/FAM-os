import unittest
from datetime import datetime, timezone

from fam_os.supervisor import (
    AuditEmissionError,
    AuditedOwnedServiceLifecycle,
    GENESIS_AUDIT_DIGEST,
    InMemoryServiceOwnershipRegistry,
    OwnedServiceLifecycle,
    ServiceDefinition,
    ServiceLifecycleError,
    ServiceState,
    ServiceStatus,
    SupervisorAuditEmitter,
    SupervisorAuditOperation,
    SupervisorAuditOutcome,
    SupervisorAuthorizationError,
    SupervisorCallContext,
)
from fam_os.supervisor.audit_codec import create_audit_record


NOW = datetime(2026, 7, 16, tzinfo=timezone.utc)


class SequenceSink:
    def __init__(self, fail_on: int | None = None) -> None:
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
    def __init__(self, state=ServiceState.INACTIVE, fail_start=False) -> None:
        self.state = state
        self.fail_start = fail_start
        self.starts = 0
        self.stops = 0

    def start(self, definition):
        self.starts += 1
        if self.fail_start:
            raise ServiceLifecycleError("start failed")
        self.state = ServiceState.ACTIVE
        return self.status(definition.service_id)

    def stop(self, service_id):
        self.stops += 1
        self.state = ServiceState.INACTIVE
        return self.status(service_id)

    def status(self, service_id):
        return ServiceStatus(service_id, self.state)


class Authorizer:
    def __init__(self, deny=False) -> None:
        self.deny = deny

    def require(self, context, capability, service_id):
        if self.deny:
            raise SupervisorAuthorizationError("denied")


def context() -> SupervisorCallContext:
    return SupervisorCallContext("request-1", "principal-1", "session-1", "authority-1")


def use_case(lifecycle, sink, authorizer=None):
    owned = OwnedServiceLifecycle(
        lifecycle, authorizer or Authorizer(), InMemoryServiceOwnershipRegistry()
    )
    emitter = SupervisorAuditEmitter(
        sink, clock=lambda: NOW,
        event_id_factory=lambda: f"event-{len(sink.records) + 1}",
    )
    return AuditedOwnedServiceLifecycle(owned, emitter)


class AuditedOwnedServiceLifecycleTests(unittest.TestCase):
    def test_start_has_durable_requested_and_succeeded_records(self) -> None:
        sink = SequenceSink()
        lifecycle = FakeLifecycle()
        status = use_case(lifecycle, sink).start(
            context(), ServiceDefinition("fam-audit-test", ("/usr/bin/true",))
        )
        self.assertEqual(ServiceState.ACTIVE, status.state)
        self.assertEqual(1, lifecycle.starts)
        self.assertEqual(
            [SupervisorAuditOutcome.REQUESTED, SupervisorAuditOutcome.SUCCEEDED],
            [record.intent.outcome for record in sink.records],
        )
        self.assertTrue(all(
            record.intent.operation is SupervisorAuditOperation.SERVICE_START
            for record in sink.records
        ))
        self.assertNotEqual(
            sink.records[0].intent.event_id, sink.records[1].intent.event_id
        )
        self.assertEqual(
            sink.records[0].intent.operation_id,
            sink.records[1].intent.operation_id,
        )

    def test_request_audit_failure_prevents_start(self) -> None:
        lifecycle = FakeLifecycle()
        with self.assertRaises(AuditEmissionError):
            use_case(lifecycle, SequenceSink(fail_on=1)).start(
                context(), ServiceDefinition("fam-audit-test", ("/usr/bin/true",))
            )
        self.assertEqual(0, lifecycle.starts)

    def test_outcome_audit_failure_compensates_new_start(self) -> None:
        lifecycle = FakeLifecycle()
        with self.assertRaises(AuditEmissionError):
            use_case(lifecycle, SequenceSink(fail_on=2)).start(
                context(), ServiceDefinition("fam-audit-test", ("/usr/bin/true",))
            )
        self.assertEqual((1, 1), (lifecycle.starts, lifecycle.stops))
        self.assertEqual(ServiceState.INACTIVE, lifecycle.state)

    def test_outcome_failure_does_not_stop_preexisting_service(self) -> None:
        lifecycle = FakeLifecycle(ServiceState.ACTIVE)
        with self.assertRaises(AuditEmissionError):
            use_case(lifecycle, SequenceSink(fail_on=2)).start(
                context(), ServiceDefinition("fam-audit-test", ("/usr/bin/true",))
            )
        self.assertEqual((0, 0), (lifecycle.starts, lifecycle.stops))
        self.assertEqual(ServiceState.ACTIVE, lifecycle.state)

    def test_denial_is_recorded_without_raw_exception(self) -> None:
        sink = SequenceSink()
        with self.assertRaises(SupervisorAuthorizationError):
            use_case(FakeLifecycle(), sink, Authorizer(deny=True)).start(
                context(), ServiceDefinition("fam-audit-test", ("/usr/bin/true",))
            )
        denied = sink.records[-1].intent
        self.assertEqual(SupervisorAuditOutcome.DENIED, denied.outcome)
        self.assertEqual("authorization.denied", denied.reason_code)


if __name__ == "__main__":
    unittest.main()
