import unittest

from fam_os.supervisor import (
    BlockIoBandwidthCeiling,
    BlockIoBandwidthLimit,
    CountCeiling,
    CpuQuotaCeiling,
    LimitVerificationStatus,
    ResourceCeiling,
    ResourceLimits,
    ResourceSnapshot,
    verify_applied_limits,
)


def snapshot(
    *, memory: int = 64, swap: int = 0, cpu: float = 25.0, tasks: int = 8
) -> ResourceSnapshot:
    return ResourceSnapshot(
        "fam-test",
        memory_limit=ResourceCeiling(memory),
        swap_limit=ResourceCeiling(swap),
        cpu_quota=CpuQuotaCeiling(cpu),
        tasks_limit=CountCeiling(tasks),
    )


class AppliedResourceLimitTests(unittest.TestCase):
    def test_exact_cpu_memory_swap_and_task_limits_pass(self) -> None:
        limits = ResourceLimits(64, 0, 25.0, 8)
        verification = verify_applied_limits(limits, snapshot(), "fam-test")
        self.assertTrue(verification.passed)
        self.assertTrue(
            all(check.status is LimitVerificationStatus.MATCHED for check in verification.checks)
        )

    def test_missing_or_mismatched_limit_fails_closed(self) -> None:
        limits = ResourceLimits(64, 0, 25.0, 8)
        missing = verify_applied_limits(limits, None, "fam-test")
        mismatch = verify_applied_limits(
            limits, snapshot(memory=128), "fam-test"
        )
        self.assertFalse(missing.passed)
        self.assertFalse(mismatch.passed)
        self.assertIn(
            LimitVerificationStatus.UNAVAILABLE,
            {check.status for check in missing.checks},
        )
        self.assertIn(
            LimitVerificationStatus.MISMATCHED,
            {check.status for check in mismatch.checks},
        )

    def test_unrequested_limits_do_not_claim_a_constrained_service(self) -> None:
        verification = verify_applied_limits(
            ResourceLimits(), ResourceSnapshot("fam-test"), "fam-test"
        )
        self.assertFalse(verification.passed)
        self.assertTrue(
            all(
                check.status is LimitVerificationStatus.NOT_REQUESTED
                for check in verification.checks
            )
        )

    def test_explicit_unbounded_ceiling_is_mismatch_not_unavailable(self) -> None:
        unbounded = ResourceSnapshot(
            "fam-test",
            memory_limit=ResourceCeiling(None),
            swap_limit=ResourceCeiling(0),
            cpu_quota=CpuQuotaCeiling(25.0),
            tasks_limit=CountCeiling(8),
        )
        verification = verify_applied_limits(
            ResourceLimits(64, 0, 25.0, 8), unbounded, "fam-test"
        )
        memory = next(
            check for check in verification.checks if check.resource == "memory_max_bytes"
        )
        self.assertIs(memory.status, LimitVerificationStatus.MISMATCHED)
        self.assertIsNone(memory.applied)

    def test_block_io_bandwidth_matches_and_unavailable_fails_closed(self) -> None:
        limit = BlockIoBandwidthLimit(
            "/dev/nvme0n1", 259, 0, 1_000_000_000, 256_000_000
        )
        limits = ResourceLimits(memory_max_bytes=64, block_io_bandwidth=(limit,))
        observed = snapshot()
        observed = ResourceSnapshot(
            observed.service_id, memory_limit=observed.memory_limit,
            swap_limit=observed.swap_limit, cpu_quota=observed.cpu_quota,
            tasks_limit=observed.tasks_limit,
            block_io_limits=(
                BlockIoBandwidthCeiling(259, 0, 1_000_000_000, 256_000_000),
            ),
        )
        self.assertTrue(verify_applied_limits(limits, observed, "fam-test").passed)
        unavailable = ResourceSnapshot("fam-test", memory_limit=ResourceCeiling(64))
        self.assertFalse(verify_applied_limits(limits, unavailable, "fam-test").passed)


if __name__ == "__main__":
    unittest.main()
