"""Opt-in live smoke for ownership-aware unprivileged service lifecycle."""

from __future__ import annotations

import os
import unittest

from fam_os.adapters.linux.command import SubprocessCommandRunner
from fam_os.adapters.systemd.lifecycle import SystemdUserServiceLifecycle
from fam_os.supervisor import (
    InMemoryServiceOwnershipRegistry,
    OwnedServiceLifecycle,
    ServiceDefinition,
    ServiceState,
    SupervisorCallContext,
    SupervisorCapability,
)


class ExactSmokeAuthorizer:
    def require(self, context, capability, service_id) -> None:
        if context.authority_ref != "phase32-smoke-authority":
            raise AssertionError("unexpected authority")
        if capability not in {
            SupervisorCapability.START_UNPRIVILEGED_SERVICE,
            SupervisorCapability.STOP_OWNED_SERVICE,
            SupervisorCapability.READ_OWNED_SERVICE_STATUS,
        }:
            raise AssertionError("unexpected capability")
        if service_id != "fam-phase32-smoke":
            raise AssertionError("unexpected service")


@unittest.skipUnless(
    os.environ.get("FAM_OWNED_LIFECYCLE_SMOKE") == "1",
    "set FAM_OWNED_LIFECYCLE_SMOKE=1 for the live user-service test",
)
class OwnedServiceLifecycleSmokeTests(unittest.TestCase):
    def test_owned_dummy_service_is_started_observed_and_stopped(self) -> None:
        adapter = SystemdUserServiceLifecycle(SubprocessCommandRunner())
        use_case = OwnedServiceLifecycle(
            adapter, ExactSmokeAuthorizer(), InMemoryServiceOwnershipRegistry()
        )
        context = SupervisorCallContext(
            "phase32-request",
            "local-principal",
            "local-session",
            "phase32-smoke-authority",
        )
        definition = ServiceDefinition(
            "fam-phase32-smoke", ("/usr/bin/sleep", "20")
        )
        try:
            self.assertEqual(ServiceState.ACTIVE, use_case.start(context, definition).state)
            self.assertEqual(
                ServiceState.ACTIVE,
                use_case.status(context, definition.service_id).state,
            )
        finally:
            use_case.stop(context, definition.service_id)
        self.assertEqual(
            ServiceState.INACTIVE,
            adapter.status(definition.service_id).state,
        )


if __name__ == "__main__":
    unittest.main()
