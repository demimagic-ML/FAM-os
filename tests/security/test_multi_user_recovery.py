import os
import stat
import tempfile
import unittest
from pathlib import Path

from fam_os.product.recovery_mode import RecoveryModePolicy, RecoveryOperation
from fam_os.product.user_isolation import PrivateUserRuntime, UserRuntimeIdentity


class MultiUserRecoveryTests(unittest.TestCase):
    def test_runtime_is_owned_by_effective_user_and_private(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory, "fam")
            runtime = PrivateUserRuntime(root, UserRuntimeIdentity("owner", os.geteuid()))
            runtime.initialize()
            self.assertEqual(root.stat().st_uid, os.geteuid())
            self.assertEqual(stat.S_IMODE(root.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE((root / "memory").stat().st_mode), 0o700)

    def test_runtime_rejects_different_uid_and_unsafe_name(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = PrivateUserRuntime(
                Path(directory, "fam"), UserRuntimeIdentity("other", os.geteuid() + 1),
            )
            with self.assertRaisesRegex(PermissionError, "effective UID"):
                runtime.initialize()
        with tempfile.TemporaryDirectory() as directory:
            runtime = PrivateUserRuntime(
                Path(directory, "fam"), UserRuntimeIdentity("owner", os.geteuid()),
            )
            runtime.initialize()
            with self.assertRaisesRegex(ValueError, "safe component"):
                runtime.private_path("memory", "../other")

    def test_recovery_is_offline_and_denies_runtime_side_effects(self) -> None:
        policy = RecoveryModePolicy()
        for operation in RecoveryOperation:
            decision = policy.decide(operation)
            self.assertFalse(decision.network_allowed)
            if operation in {
                RecoveryOperation.DIAGNOSE, RecoveryOperation.EXPORT_AUDIT,
                RecoveryOperation.EXPORT_MEMORY, RecoveryOperation.ROLLBACK_RELEASE,
                RecoveryOperation.REPAIR_STATE,
            }:
                self.assertTrue(decision.allowed)
            else:
                self.assertFalse(decision.allowed)


if __name__ == "__main__":
    unittest.main()
