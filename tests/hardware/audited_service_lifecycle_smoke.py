"""Opt-in live proof of durable audit linkage for a real user service."""

from __future__ import annotations

import itertools
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from fam_os.adapters.audit import JsonlHashChainAuditSink
from fam_os.adapters.linux.command import SubprocessCommandRunner
from fam_os.adapters.systemd import SystemdUserServiceLifecycle
from fam_os.supervisor import (
    AuditedOwnedServiceLifecycle,
    InMemoryServiceOwnershipRegistry,
    OwnedServiceLifecycle,
    ServiceDefinition,
    ServiceState,
    SupervisorAuditEmitter,
    SupervisorAuditOperation,
    SupervisorAuditOutcome,
    SupervisorCallContext,
    SupervisorCapability,
)
from fam_os.supervisor.audit_codec import decode_audit_record


SERVICE_ID = "fam-phase35-smoke"


class ExactAuthorizer:
    def require(self, context, capability, service_id) -> None:
        expected = {
            SupervisorCapability.START_UNPRIVILEGED_SERVICE,
            SupervisorCapability.STOP_OWNED_SERVICE,
        }
        if capability not in expected or service_id != SERVICE_ID:
            raise AssertionError("unexpected audited-service authority")


@unittest.skipUnless(
    os.environ.get("FAM_AUDIT_LIFECYCLE_SMOKE") == "1",
    "set FAM_AUDIT_LIFECYCLE_SMOKE=1 for the live audit test",
)
class AuditedServiceLifecycleSmokeTests(unittest.TestCase):
    def test_real_start_and_stop_are_durably_hash_chained(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            sink = JsonlHashChainAuditSink(Path(directory) / "audit.jsonl")
            lifecycle = SystemdUserServiceLifecycle(SubprocessCommandRunner())
            owned = OwnedServiceLifecycle(
                lifecycle, ExactAuthorizer(), InMemoryServiceOwnershipRegistry()
            )
            sequence = itertools.count(1)
            audit = SupervisorAuditEmitter(
                sink,
                clock=lambda: datetime.now(timezone.utc),
                event_id_factory=lambda: f"phase35-event-{next(sequence)}",
            )
            use_case = AuditedOwnedServiceLifecycle(owned, audit)
            context = SupervisorCallContext(
                "phase35-request", "local-principal", "local-session",
                "phase35-authority",
            )
            definition = ServiceDefinition(SERVICE_ID, ("/usr/bin/sleep", "15"))
            try:
                self.assertEqual(ServiceState.ACTIVE, use_case.start(context, definition).state)
                self.assertEqual(ServiceState.INACTIVE, use_case.stop(context, SERVICE_ID).state)
            finally:
                if lifecycle.status(SERVICE_ID).state is ServiceState.ACTIVE:
                    lifecycle.stop(SERVICE_ID)
            self.assertEqual(_expected_events(), _read_events(sink.path))
            verification = sink.verify()
            self.assertTrue(verification.passed)
            self.assertEqual(4, verification.record_count)
            self.assertEqual(0o600, sink.path.stat().st_mode & 0o777)


def _read_events(path: Path):
    records = tuple(decode_audit_record(line) for line in path.read_bytes().splitlines())
    return tuple((record.intent.operation, record.intent.outcome) for record in records)


def _expected_events():
    return (
        (SupervisorAuditOperation.SERVICE_START, SupervisorAuditOutcome.REQUESTED),
        (SupervisorAuditOperation.SERVICE_START, SupervisorAuditOutcome.SUCCEEDED),
        (SupervisorAuditOperation.SERVICE_STOP, SupervisorAuditOutcome.REQUESTED),
        (SupervisorAuditOperation.SERVICE_STOP, SupervisorAuditOutcome.SUCCEEDED),
    )


if __name__ == "__main__":
    unittest.main()
