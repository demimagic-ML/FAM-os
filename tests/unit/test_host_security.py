import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fam_os.product.host_security import (
    FAM_USERNS_APPARMOR_PROFILE,
    diagnose_verifier_sandbox,
    required_sandbox_apparmor_profile,
)
from fam_os.verification import IsolationLevel, SandboxResult, SandboxStatus


class HostSecurityTests(unittest.TestCase):
    def test_selects_dedicated_profile_only_for_restricted_apparmor_host(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            enabled = root / "enabled"
            restricted = root / "restricted"
            enabled.write_text("Y\n", encoding="utf-8")
            restricted.write_text("1\n", encoding="utf-8")

            self.assertEqual(
                FAM_USERNS_APPARMOR_PROFILE,
                required_sandbox_apparmor_profile(enabled, restricted),
            )
            restricted.write_text("0\n", encoding="utf-8")
            self.assertIsNone(
                required_sandbox_apparmor_profile(enabled, restricted),
            )

    def test_missing_host_policy_files_do_not_require_profile(self) -> None:
        missing = Path("/definitely/missing/fam-os-policy")
        self.assertIsNone(required_sandbox_apparmor_profile(missing, missing))

    def test_diagnosis_requires_real_bubblewrap_sentinel(self) -> None:
        result = SandboxResult(
            SandboxStatus.COMPLETED, IsolationLevel.BUBBLEWRAP, .1,
            stdout="FAM_SANDBOX_READY\n", exit_code=0,
        )
        with (
            patch(
                "fam_os.product.host_security.required_sandbox_apparmor_profile",
                return_value="fam-os-userns",
            ),
            patch("fam_os.product.host_security.BubblewrapSandboxRunner") as runner,
        ):
            runner.return_value.run.return_value = result
            receipt = diagnose_verifier_sandbox()

        self.assertTrue(receipt.healthy)
        self.assertEqual("fam-os-userns", receipt.apparmor_profile)
        self.assertEqual("bubblewrap", receipt.isolation)


if __name__ == "__main__":
    unittest.main()
