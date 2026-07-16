"""Opt-in live proof that requested user-service limits match cgroup state."""

from __future__ import annotations

import os
import unittest

from fam_os.adapters.cgroup.observer import CgroupV2ResourceObserver
from fam_os.adapters.linux.command import SubprocessCommandRunner
from fam_os.adapters.systemd.lifecycle import SystemdUserServiceLifecycle
from fam_os.supervisor import (
    ConstrainedServiceLifecycle,
    InMemoryServiceOwnershipRegistry,
    OwnedServiceLifecycle,
    ResourceLimits,
    ServiceDefinition,
    ServiceState,
    SupervisorCallContext,
    SupervisorCapability,
)


class ExactAuthorizer:
    def require(self, context, capability, service_id) -> None:
        expected = {
            SupervisorCapability.APPLY_SERVICE_RESOURCE_LIMITS,
            SupervisorCapability.START_UNPRIVILEGED_SERVICE,
            SupervisorCapability.STOP_OWNED_SERVICE,
        }
        if capability not in expected or service_id != "fam-phase33-smoke":
            raise AssertionError("unexpected constrained-service authority")


@unittest.skipUnless(
    os.environ.get("FAM_CONSTRAINED_SERVICE_SMOKE") == "1",
    "set FAM_CONSTRAINED_SERVICE_SMOKE=1 for the live cgroup-limit test",
)
class ConstrainedServiceSmokeTests(unittest.TestCase):
    def test_applied_cpu_memory_swap_and_tasks_match_request(self) -> None:
        adapter = SystemdUserServiceLifecycle(SubprocessCommandRunner())
        owned = OwnedServiceLifecycle(
            adapter, ExactAuthorizer(), InMemoryServiceOwnershipRegistry()
        )
        use_case = ConstrainedServiceLifecycle(
            owned, CgroupV2ResourceObserver(adapter)
        )
        context = SupervisorCallContext(
            "phase33-request", "local-principal", "local-session", "phase33-authority"
        )
        definition = ServiceDefinition(
            "fam-phase33-smoke",
            ("/usr/bin/sleep", "20"),
            limits=ResourceLimits(64 * 1024**2, 0, 25.0, 8),
        )
        try:
            outcome = use_case.start(context, definition)
            self.assertTrue(outcome.constrained)
            self.assertTrue(outcome.verification.passed)
        finally:
            owned.stop(context, definition.service_id)
        self.assertEqual(ServiceState.INACTIVE, adapter.status(definition.service_id).state)


if __name__ == "__main__":
    unittest.main()
