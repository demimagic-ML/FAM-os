"""Opt-in live proof that a failed user service reaches an audited safe baseline."""

from __future__ import annotations

import os
import tempfile
import time
import unittest
from pathlib import Path

from fam_os.adapters.audit import JsonlHashChainAuditSink
from fam_os.adapters.linux.command import SubprocessCommandRunner
from fam_os.adapters.systemd import SystemdUserServiceLifecycle, SystemdUserSettings
from fam_os.supervisor import (
    AccessMode,
    AccessResourceDescriptor,
    AccessResourceKind,
    AuditedOwnedServiceLifecycle,
    AuditedServiceAccessController,
    InMemoryAccessGrantRegistry,
    InMemoryAccessResourceCatalog,
    InMemoryServiceOwnershipRegistry,
    OwnedService,
    OwnedServiceLifecycle,
    ServiceAccessController,
    ServiceDefinition,
    ServiceRecoveryController,
    ServiceState,
    SupervisorAuditEmitter,
    SupervisorCallContext,
    SupervisorCapability,
)


SERVICE_ID = "fam-phase36-failed-smoke"


class ExactAuthorizer:
    def require(self, context, capability, service_id):
        expected = {
            SupervisorCapability.RECOVER_FAILED_SERVICE,
            SupervisorCapability.STOP_OWNED_SERVICE,
        }
        if capability not in expected or service_id != SERVICE_ID:
            raise AssertionError("unexpected recovery authority")


class NoAccessAdapter:
    def grant(self, grant, resource):
        raise AssertionError("recovery smoke has no access grants")

    def revoke(self, grant, resource):
        raise AssertionError("recovery smoke has no access grants")


class NoResourceObserver:
    def observe(self, service_id):
        return None


@unittest.skipUnless(
    os.environ.get("FAM_SERVICE_RECOVERY_SMOKE") == "1",
    "set FAM_SERVICE_RECOVERY_SMOKE=1 for the live recovery test",
)
class ServiceRecoverySmokeTests(unittest.TestCase):
    def test_failed_transient_service_recovers_to_inactive(self):
        with tempfile.TemporaryDirectory() as directory:
            lifecycle = SystemdUserServiceLifecycle(
                SubprocessCommandRunner(),
                SystemdUserSettings(retain_failed_state=True),
            )
            ownership = InMemoryServiceOwnershipRegistry()
            definition = ServiceDefinition(
                SERVICE_ID, ("/usr/bin/sh", "-c", "sleep 0.1; exit 7")
            )
            ownership.claim(OwnedService("local-principal", "local-session", definition))
            authorizer = ExactAuthorizer()
            sink = JsonlHashChainAuditSink(Path(directory) / "recovery.jsonl")
            audit = SupervisorAuditEmitter(sink)
            owned = OwnedServiceLifecycle(lifecycle, authorizer, ownership)
            access = _access(authorizer, ownership, audit)
            recovery = ServiceRecoveryController(
                AuditedOwnedServiceLifecycle(owned, audit), access,
                NoResourceObserver(), lifecycle, audit,
            )
            context = SupervisorCallContext(
                "phase36-request", "local-principal", "local-session",
                "phase36-authority",
            )
            try:
                lifecycle.start(definition)
                self.assertEqual(ServiceState.FAILED, _wait_failed(lifecycle).state)
                report = recovery.recover_failed(context, SERVICE_ID)
                self.assertEqual(ServiceState.INACTIVE, report.final_status.state)
            finally:
                if lifecycle.status(SERVICE_ID).state in {
                    ServiceState.ACTIVE, ServiceState.ACTIVATING, ServiceState.FAILED,
                }:
                    lifecycle.stop(SERVICE_ID)
            verification = sink.verify()
            self.assertTrue(verification.passed)
            self.assertEqual(2, verification.record_count)
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


def _wait_failed(lifecycle):
    deadline = time.monotonic() + 3.0
    status = lifecycle.status(SERVICE_ID)
    while status.state in {ServiceState.ACTIVE, ServiceState.ACTIVATING}:
        if time.monotonic() >= deadline:
            break
        time.sleep(0.02)
        status = lifecycle.status(SERVICE_ID)
    return status


if __name__ == "__main__":
    unittest.main()
