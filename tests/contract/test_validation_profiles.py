import copy
import json
import unittest
from dataclasses import replace
from pathlib import Path

from fam_os.scheduler import (
    AcceleratorVisibility,
    COMPAT_CPU_16GB_PROFILE_ID,
    ConfigurationCompositionRequest,
    FULL_REFERENCE_WORKSTATION_PROFILE_ID,
    ValidationProfileDocument,
    compose_resource_configuration,
)
from fam_os.schemas import SchemaValidationError, decode_document, encode_document, loads_document
from tests.contract.schema_configuration_fixtures import discovered_state, scheduler_defaults
from tests.contract.schema_manifest_fixtures import GIB


PROFILE_ROOT = Path("configs/profiles")


def load_profile(filename: str) -> ValidationProfileDocument:
    value = loads_document((PROFILE_ROOT / filename).read_text(encoding="utf-8"))
    if not isinstance(value, ValidationProfileDocument):
        raise TypeError("profile document decoded to the wrong domain type")
    return value


def compose(profile: ValidationProfileDocument):
    state = discovered_state()
    if profile.service.memory_max_bytes is not None:
        state = replace(state, cgroup_memory_limit_bytes=profile.service.memory_max_bytes)
    state = replace(state, swap_limit_bytes=profile.service.swap_max_bytes)
    request = ConfigurationCompositionRequest(
        f"budget.{profile.profile_id}",
        scheduler_defaults(),
        state,
        profile.configuration,
    )
    return compose_resource_configuration(request)


class ValidationProfileDocumentTests(unittest.TestCase):
    def test_compatibility_profile_has_exact_minimum_service_envelope(self) -> None:
        profile = load_profile("compat-cpu-16gb.json")
        self.assertEqual(COMPAT_CPU_16GB_PROFILE_ID, profile.profile_id)
        self.assertEqual(16 * GIB, profile.service.memory_max_bytes)
        self.assertEqual(0, profile.service.swap_max_bytes)
        self.assertEqual(AcceleratorVisibility.DENY_ALL, profile.service.accelerator_visibility)
        self.assertFalse(profile.configuration.policy.accelerator_allowed)

    def test_compatibility_profile_composes_visible_gpu_as_disallowed(self) -> None:
        result = compose(load_profile("compat-cpu-16gb.json"))
        self.assertEqual(16 * GIB, result.budget.memory.effective_limit_bytes)
        self.assertEqual(14 * GIB, result.budget.memory.scheduler_limit_bytes)
        self.assertEqual(2 * GIB, result.budget.memory.reserved_headroom_bytes)
        self.assertEqual(0, result.budget.memory.swap_limit_bytes)
        self.assertFalse(result.budget.accelerators[0].placement_allowed)
        self.assertEqual(0, result.budget.accelerators[0].scheduler_memory_limit_bytes)

    def test_full_profile_has_no_artificial_memory_or_cpu_ceiling(self) -> None:
        profile = load_profile("full-reference-workstation.json")
        self.assertEqual(FULL_REFERENCE_WORKSTATION_PROFILE_ID, profile.profile_id)
        self.assertIsNone(profile.service.memory_max_bytes)
        self.assertIsNone(profile.service.cpu_quota_cores)
        self.assertIsNone(profile.configuration.policy.max_memory_bytes)
        self.assertIsNone(profile.configuration.policy.max_cpu_cores)
        self.assertEqual(AcceleratorVisibility.DISCOVERED, profile.service.accelerator_visibility)

    def test_full_profile_composes_cpu_ram_vram_and_nvme_tiers(self) -> None:
        result = compose(load_profile("full-reference-workstation.json"))
        self.assertGreater(result.budget.cpu.scheduler_quota_cores, 8)
        self.assertGreater(result.budget.memory.scheduler_limit_bytes, 16 * GIB)
        self.assertTrue(result.budget.accelerators[0].placement_allowed)
        self.assertGreater(result.budget.accelerators[0].scheduler_memory_limit_bytes, 0)
        self.assertGreater(result.budget.storage[0].scheduler_cache_limit_bytes, 0)

    def test_profile_files_are_exact_schema_documents(self) -> None:
        for filename in ("compat-cpu-16gb.json", "full-reference-workstation.json"):
            with self.subTest(filename=filename):
                raw = json.loads((PROFILE_ROOT / filename).read_text(encoding="utf-8"))
                self.assertEqual(raw, encode_document(load_profile(filename)))

    def test_full_profile_contains_no_captured_machine_identifiers(self) -> None:
        raw = (PROFILE_ROOT / "full-reference-workstation.json").read_text(encoding="utf-8")
        for forbidden in ("gpu-0", "nvme-root", "/home/", "RTX 5080", "ollama"):
            self.assertNotIn(forbidden, raw)

    def test_decoder_rejects_changed_compatibility_ceiling(self) -> None:
        document = encode_document(load_profile("compat-cpu-16gb.json"))
        document = copy.deepcopy(document)
        document["payload"]["service"]["memory_max_bytes"] = 15 * GIB
        with self.assertRaises(SchemaValidationError):
            decode_document(document)

    def test_decoder_rejects_full_profile_with_compatibility_ceiling(self) -> None:
        document = encode_document(load_profile("full-reference-workstation.json"))
        document = copy.deepcopy(document)
        document["payload"]["service"]["memory_max_bytes"] = 16 * GIB
        with self.assertRaises(SchemaValidationError):
            decode_document(document)


if __name__ == "__main__":
    unittest.main()
