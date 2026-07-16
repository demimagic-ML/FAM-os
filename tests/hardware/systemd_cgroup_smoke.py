"""Opt-in live smoke test for user-systemd lifecycle and cgroup observation."""

import os
import unittest

from fam_os.adapters.cgroup import CgroupV2ResourceObserver
from fam_os.adapters.linux.command import SubprocessCommandRunner
from fam_os.adapters.systemd import SystemdUserServiceLifecycle
from fam_os.supervisor import ResourceLimits, ServiceDefinition, ServiceState


@unittest.skipUnless(os.getenv("FAM_SYSTEMD_SMOKE") == "1", "live systemd smoke disabled")
class SystemdCgroupSmokeTests(unittest.TestCase):
    def test_bounded_dummy_service_lifecycle(self) -> None:
        lifecycle = SystemdUserServiceLifecycle(SubprocessCommandRunner())
        observer = CgroupV2ResourceObserver(lifecycle)
        definition = ServiceDefinition(
            service_id="fam-phase17-smoke",
            command=("/usr/bin/sleep", "20"),
            environment=(("FAM_SMOKE", "1"),),
            limits=ResourceLimits(
                memory_max_bytes=64 * 1024**2,
                swap_max_bytes=0,
                cpu_quota_percent=25,
                tasks_max=8,
            ),
        )

        try:
            status = lifecycle.start(definition)
            snapshot = observer.observe(definition.service_id)
            self.assertEqual(status.state, ServiceState.ACTIVE)
            self.assertIsNotNone(snapshot)
            self.assertEqual(snapshot.memory_limit.maximum_bytes, 64 * 1024**2)
            self.assertEqual(snapshot.swap_limit.maximum_bytes, 0)
        finally:
            lifecycle.stop(definition.service_id)


if __name__ == "__main__":
    unittest.main()
