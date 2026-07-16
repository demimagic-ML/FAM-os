import unittest

from fam_os.supervisor import (
    ResourceCeiling,
    ResourceEvent,
    ResourceLimits,
    ResourceSnapshot,
    ServiceDefinition,
)


class SupervisorContractTests(unittest.TestCase):
    def test_rejects_unsafe_service_identity(self) -> None:
        with self.assertRaisesRegex(ValueError, "service_id"):
            ServiceDefinition("../unsafe", ("/usr/bin/true",))

    def test_rejects_duplicate_environment_keys(self) -> None:
        with self.assertRaisesRegex(ValueError, "unique"):
            ServiceDefinition(
                "fam-test", ("/usr/bin/true",), (("MODE", "one"), ("MODE", "two"))
            )

    def test_validates_resource_limits(self) -> None:
        with self.assertRaisesRegex(ValueError, "cpu_quota"):
            ResourceLimits(cpu_quota_percent=0)
        with self.assertRaisesRegex(ValueError, "tasks_max"):
            ResourceLimits(tasks_max=-1)

    def test_distinguishes_unbounded_from_unavailable_ceiling(self) -> None:
        snapshot = ResourceSnapshot("fam-test", memory_limit=ResourceCeiling(None))
        self.assertTrue(snapshot.memory_limit.unbounded)
        self.assertIsNone(ResourceSnapshot("fam-other").memory_limit)

    def test_finds_resource_event_count(self) -> None:
        snapshot = ResourceSnapshot("fam-test", events=(ResourceEvent("oom_kill", 2),))
        self.assertEqual(snapshot.event_count("oom_kill"), 2)
        self.assertIsNone(snapshot.event_count("high"))


if __name__ == "__main__":
    unittest.main()
