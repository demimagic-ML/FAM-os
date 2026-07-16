"""Opt-in combined live proof of the Phase 3 Supervisor exit gate."""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from fam_os.adapters.audit import JsonlHashChainAuditSink
from fam_os.adapters.cgroup import CgroupV2ResourceObserver
from fam_os.adapters.linux.command import SubprocessCommandRunner
from fam_os.adapters.systemd import SystemdUserServiceLifecycle
from fam_os.supervisor import (
    AccessMode,
    AccessResourceDescriptor,
    AccessResourceKind,
    AuditedConstrainedServiceLifecycle,
    AuditedOwnedServiceLifecycle,
    AuditedServiceAccessController,
    ConstrainedServiceLifecycle,
    InMemoryAccessGrantRegistry,
    InMemoryAccessResourceCatalog,
    InMemoryServiceOwnershipRegistry,
    OwnedServiceLifecycle,
    ResourceLimits,
    ServiceAccessController,
    ServiceDefinition,
    ServiceRecoveryController,
    ServiceState,
    ServiceTerminationReason,
    SupervisorAuditEmitter,
    SupervisorCallContext,
    SupervisorCapability,
)


SERVICE_ID = "fam-phase3-exit-smoke"


class ExactAuthorizer:
    def require(self, context, capability, service_id):
        expected = {
            SupervisorCapability.START_UNPRIVILEGED_SERVICE,
            SupervisorCapability.STOP_OWNED_SERVICE,
            SupervisorCapability.APPLY_SERVICE_RESOURCE_LIMITS,
            SupervisorCapability.SAFE_TERMINATE_OWNED_SERVICE,
        }
        if capability not in expected or service_id != SERVICE_ID:
            raise AssertionError("unexpected Phase 3 authority")


class NoAccessAdapter:
    def grant(self, grant, resource):
        raise AssertionError("exit smoke has no access grants")

    def revoke(self, grant, resource):
        raise AssertionError("exit smoke has no access grants")


@unittest.skipUnless(
    os.environ.get("FAM_SUPERVISOR_PHASE3_SMOKE") == "1",
    "set FAM_SUPERVISOR_PHASE3_SMOKE=1 for the combined Phase 3 test",
)
class SupervisorPhase3ExitSmokeTests(unittest.TestCase):
    def test_start_constrain_observe_audit_and_terminate(self):
        with tempfile.TemporaryDirectory() as directory:
            raw = SystemdUserServiceLifecycle(SubprocessCommandRunner())
            observer = CgroupV2ResourceObserver(raw)
            authorizer = ExactAuthorizer()
            ownership = InMemoryServiceOwnershipRegistry()
            sink = JsonlHashChainAuditSink(Path(directory) / "supervisor.jsonl")
            audit = SupervisorAuditEmitter(sink)
            owned = OwnedServiceLifecycle(raw, authorizer, ownership)
            audited = AuditedOwnedServiceLifecycle(owned, audit)
            constrained = AuditedConstrainedServiceLifecycle(
                ConstrainedServiceLifecycle(audited, observer), audit
            )
            recovery = ServiceRecoveryController(
                audited, _access(authorizer, ownership, audit), observer, raw, audit
            )
            context = SupervisorCallContext(
                "phase3-exit-request", "local-principal", "local-session",
                "phase3-exit-authority",
            )
            definition = ServiceDefinition(
                SERVICE_ID, ("/usr/bin/sleep", "15"),
                limits=ResourceLimits(64 * 1024**2, 0, 25.0, 8),
            )
            try:
                started = constrained.start(context, definition)
                self.assertTrue(started.constrained)
                observed = observer.observe(SERVICE_ID)
                self.assertIsNotNone(observed)
                self.assertEqual(64 * 1024**2, observed.memory_limit.maximum_bytes)
                report = recovery.terminate(
                    context, SERVICE_ID,
                    ServiceTerminationReason.SUPERVISOR_SHUTDOWN,
                )
                self.assertEqual(ServiceState.INACTIVE, report.final_status.state)
            finally:
                if raw.status(SERVICE_ID).state is ServiceState.ACTIVE:
                    raw.stop(SERVICE_ID)
            verification = sink.verify()
            self.assertTrue(verification.passed)
            self.assertEqual(6, verification.record_count)
            self.assertEqual(0o600, sink.path.stat().st_mode & 0o777)


def _access(authorizer, ownership, audit):
    controller = ServiceAccessController(
        authorizer, ownership,
        InMemoryAccessResourceCatalog((AccessResourceDescriptor(
            "filesystem.placeholder", AccessResourceKind.FILESYSTEM,
            (AccessMode.READ,),
        ),)),
        InMemoryAccessGrantRegistry(), NoAccessAdapter(),
    )
    return AuditedServiceAccessController(controller, audit)


if __name__ == "__main__":
    unittest.main()
