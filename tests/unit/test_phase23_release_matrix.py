import tempfile
import unittest
from pathlib import Path

from tools.phase23_release_matrix.contracts import (
    HARDWARE_SUITE_PATTERN,
    PROFILES,
    select_profiles,
)
from tools.phase23_release_matrix.environment import clean_environment
from tools.phase23_release_matrix.evidence import matrix_document
from tools.phase23_release_matrix.suites import skips_are_declared


class Phase23ReleaseMatrixTests(unittest.TestCase):
    def test_default_selection_is_every_required_master_plan_profile(self) -> None:
        self.assertEqual(
            (
                "base", "verification", "mathematics", "media", "hardware",
                "training", "vscode",
            ),
            tuple(profile.name for profile in select_profiles(())),
        )
        development = next(profile for profile in PROFILES if profile.name == "development")
        self.assertFalse(development.phase23_required)
        self.assertEqual("*_smoke.py", HARDWARE_SUITE_PATTERN)

    def test_selection_rejects_unknown_and_duplicate_profiles(self) -> None:
        with self.assertRaises(ValueError):
            select_profiles(("unknown",))
        with self.assertRaises(ValueError):
            select_profiles(("base", "base"))

    def test_clean_environment_removes_checkout_import_overrides(self) -> None:
        value = clean_environment({"PATH": "/bin", "PYTHONPATH": "src", "PYTHONHOME": "/x"})
        self.assertNotIn("PYTHONPATH", value)
        self.assertNotIn("PYTHONHOME", value)
        self.assertEqual("1", value["PYTHONDONTWRITEBYTECODE"])

    def test_only_declared_environment_skips_are_accepted(self) -> None:
        declared = ({"skipped": (
            {"reason": "AT-SPI is unavailable"},
            {"reason": "set FAM_EXAMPLE_SMOKE=1 for the physical test"},
        )},)
        undeclared = ({"skipped": ({"reason": "dependency mysteriously missing"},)},)
        self.assertTrue(skips_are_declared(declared, media_installed=False))
        self.assertFalse(skips_are_declared(undeclared, media_installed=False))

    def test_matrix_pass_requires_every_profile(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            wheel = Path(directory) / "fam_os.whl"
            wheel.write_bytes(b"wheel")
            document = matrix_document(
                run_id="run", wheel=wheel, wheel_sha256="0" * 64,
                source={}, profiles=({"passed": True}, {"passed": False}),
            )
        self.assertFalse(document["passed"])


if __name__ == "__main__":
    unittest.main()
