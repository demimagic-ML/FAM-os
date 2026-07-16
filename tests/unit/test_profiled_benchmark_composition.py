import inspect
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from fam_os.adapters.systemd.commands import build_start_command
from fam_os.adapters.systemd.settings import SystemdUserSettings
from fam_os.schemas import dumps_document
from tools.parity.composition import BenchmarkComposition, load_benchmark_composition
from tools.parity.profile_service import ProfiledOllamaService, ProfiledServiceSettings
from tools.run_activation_parity import run_activation_parity
from tools.run_policy_parity import run_policy_parity
from tools.run_routing_parity import run_routing_parity
from tools.run_verified_parity import _scrub_local_paths, run_verified_parity
from tests.contract.test_validation_profiles import compose, load_profile


def benchmark_composition(filename: str) -> BenchmarkComposition:
    profile = load_profile(filename)
    return BenchmarkComposition(profile, compose(profile).budget)


class BenchmarkCompositionTests(unittest.TestCase):
    def test_placement_budget_comes_from_effective_budget(self) -> None:
        composition = benchmark_composition("compat-cpu-16gb.json")
        placement = composition.placement_budget(4096)
        self.assertEqual(composition.budget.memory.scheduler_limit_bytes, placement.memory_limit_bytes)
        self.assertEqual(0, placement.swap_limit_bytes)
        self.assertFalse(placement.gpu_allowed)

    def test_full_placement_budget_allows_discovered_accelerator(self) -> None:
        placement = benchmark_composition(
            "full-reference-workstation.json"
        ).placement_budget(8192)
        self.assertTrue(placement.gpu_allowed)
        self.assertGreater(placement.memory_limit_bytes, 16 * 1024**3)

    def test_rejects_budget_from_different_profile(self) -> None:
        compat = load_profile("compat-cpu-16gb.json")
        full_budget = compose(load_profile("full-reference-workstation.json")).budget
        with self.assertRaisesRegex(ValueError, "same profile"):
            BenchmarkComposition(compat, full_budget)

    def test_constraints_name_profile_service_and_resource_tiers(self) -> None:
        payload = benchmark_composition("full-reference-workstation.json").constraints_payload()
        self.assertEqual("full-reference-workstation", payload["profile_id"])
        self.assertIsNone(payload["service_memory_max_bytes"])
        self.assertTrue(payload["gpu_allowed"])
        self.assertTrue(payload["accelerator_budgets"])
        self.assertTrue(payload["storage_budgets"])

    def test_loader_admits_strict_profile_and_budget_documents(self) -> None:
        composition = benchmark_composition("compat-cpu-16gb.json")
        with tempfile.TemporaryDirectory() as directory:
            budget_path = Path(directory) / "budget.json"
            budget_path.write_text(dumps_document(composition.budget), encoding="utf-8")
            loaded = load_benchmark_composition(
                Path("configs/profiles/compat-cpu-16gb.json"), budget_path
            )
        self.assertEqual(composition.profile, loaded.profile)
        self.assertEqual(composition.budget, loaded.budget)

    def test_compat_profile_accepts_larger_host_when_service_commit_is_bounded(self) -> None:
        profile = load_profile("compat-cpu-16gb.json")
        budget = compose(profile).budget
        enlarged = replace(
            budget,
            memory=replace(
                budget.memory,
                effective_limit_bytes=64 * 1024**3,
                cgroup_limit_bytes=64 * 1024**3,
            ),
        )
        value = BenchmarkComposition(profile, enlarged)
        self.assertEqual(14 * 1024**3, value.budget.memory.scheduler_limit_bytes)


class ProfiledServiceDefinitionTests(unittest.TestCase):
    def definition(self, filename: str):
        settings = ProfiledServiceSettings(
            "http://127.0.0.1:11435",
            30,
            benchmark_composition(filename),
        )
        return ProfiledOllamaService(settings).definition()

    def test_compatibility_definition_enforces_cpu_only_service(self) -> None:
        definition = self.definition("compat-cpu-16gb.json")
        environment = dict(definition.environment)
        self.assertEqual("-1", environment["CUDA_VISIBLE_DEVICES"])
        self.assertEqual("cpu_avx2", environment["OLLAMA_LLM_LIBRARY"])
        self.assertEqual(16 * 1024**3, definition.limits.memory_max_bytes)
        self.assertEqual(0, definition.limits.swap_max_bytes)
        self.assertEqual(
            benchmark_composition("compat-cpu-16gb.json").budget.cpu.scheduler_quota_cores * 100,
            definition.limits.cpu_quota_percent,
        )

    def test_full_definition_does_not_inject_accelerator_disablers(self) -> None:
        definition = self.definition("full-reference-workstation.json")
        environment = dict(definition.environment)
        self.assertNotIn("CUDA_VISIBLE_DEVICES", environment)
        self.assertNotIn("GGML_VK_VISIBLE_DEVICES", environment)
        self.assertNotIn("OLLAMA_LLM_LIBRARY", environment)
        self.assertIsNone(definition.limits.memory_max_bytes)
        self.assertEqual(0, definition.limits.swap_max_bytes)

    def test_systemd_adapter_receives_only_provider_neutral_definition(self) -> None:
        definition = self.definition("compat-cpu-16gb.json")
        command = build_start_command(definition, SystemdUserSettings())
        self.assertIn("--property=MemoryMax=17179869184", command)
        self.assertIn("--property=MemorySwapMax=0", command)


class UnifiedWorkloadEntryPointTests(unittest.TestCase):
    def test_workstation_report_scrubs_local_source_paths(self) -> None:
        base = benchmark_composition("full-reference-workstation.json")
        composition = BenchmarkComposition(
            base.profile,
            base.budget,
            Path("/home/private/full-profile.json"),
            Path("/home/private/live-budget.json"),
        )
        report = {}
        _scrub_local_paths(
            report,
            Path("/home/private/smoke.json"),
            Path("/home/private/tests.py"),
            composition,
        )
        self.assertEqual("smoke.json", report["source_config"])
        self.assertEqual("tests.py", report["trusted_tests"])
        self.assertEqual("full-profile.json", report["profile_source"])
        self.assertNotIn("/home/private", repr(report))

    def test_every_parity_workload_requires_the_same_composition_type(self) -> None:
        functions = (
            run_activation_parity,
            run_policy_parity,
            run_routing_parity,
            run_verified_parity,
        )
        for function in functions:
            with self.subTest(function=function.__name__):
                parameter = inspect.signature(function).parameters["composition"]
                self.assertEqual("BenchmarkComposition", parameter.annotation)


if __name__ == "__main__":
    unittest.main()
