import unittest
from importlib.resources import files
from pathlib import Path

from fam_os.product.composition.validation_profiles import (
    SUPPORTED_VALIDATION_PROFILE_IDS,
    load_validation_profile,
    validation_profile_accelerator_environment,
    validation_profile_resource_limits,
)
from fam_os.scheduler import (
    COMPAT_CPU_16GB_PROFILE_ID,
    FULL_REFERENCE_WORKSTATION_PROFILE_ID,
)


GIB = 1024**3


class ProductValidationProfileTests(unittest.TestCase):
    def test_installed_profiles_are_exact_copies_of_canonical_configuration(self):
        packaged = files("fam_os.product.resources").joinpath("profiles")
        for profile_id in SUPPORTED_VALIDATION_PROFILE_IDS:
            with self.subTest(profile_id=profile_id):
                filename = f"{profile_id}.json"
                self.assertEqual(
                    Path("configs/profiles", filename).read_text(encoding="utf-8"),
                    packaged.joinpath(filename).read_text(encoding="utf-8"),
                )
                self.assertEqual(profile_id, load_validation_profile(profile_id).profile_id)

    def test_compat_profile_translates_service_and_scheduler_limits(self):
        profile = load_validation_profile(COMPAT_CPU_16GB_PROFILE_ID)

        limits = validation_profile_resource_limits(profile, logical_cpu_count=24)

        self.assertEqual(16 * GIB, limits.memory_max_bytes)
        self.assertEqual(14 * GIB, limits.memory_high_bytes)
        self.assertEqual(0, limits.swap_max_bytes)
        self.assertEqual(2300, limits.cpu_quota_percent)
        self.assertEqual(512, limits.tasks_max)

    def test_full_profile_removes_artificial_memory_ceiling(self):
        profile = load_validation_profile(FULL_REFERENCE_WORKSTATION_PROFILE_ID)

        limits = validation_profile_resource_limits(profile, logical_cpu_count=24)

        self.assertIsNone(limits.memory_max_bytes)
        self.assertIsNone(limits.memory_high_bytes)
        self.assertEqual(0, limits.swap_max_bytes)
        self.assertEqual(2200, limits.cpu_quota_percent)

    def test_only_compat_profile_forces_cpu_runtime(self):
        compat = validation_profile_accelerator_environment(
            load_validation_profile(COMPAT_CPU_16GB_PROFILE_ID),
        )
        full = validation_profile_accelerator_environment(
            load_validation_profile(FULL_REFERENCE_WORKSTATION_PROFILE_ID),
        )

        self.assertIn(("CUDA_VISIBLE_DEVICES", "-1"), compat)
        self.assertIn(("GGML_VK_VISIBLE_DEVICES", "-1"), compat)
        self.assertIn(("OLLAMA_LLM_LIBRARY", "cpu_avx2"), compat)
        self.assertEqual((), full)

    def test_unknown_profile_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unsupported validation profile"):
            load_validation_profile("invented-profile")


if __name__ == "__main__":
    unittest.main()
