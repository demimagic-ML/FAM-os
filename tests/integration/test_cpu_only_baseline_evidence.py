import json
import unittest
from pathlib import Path

from fam_os.scheduler import CPU_ONLY_ENVIRONMENT, CpuOnlyBaselineReport
from fam_os.scheduler.admission_contracts import AdmissionStatus
from fam_os.schemas import loads_document


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "artifacts/scheduler/phase7.5/cpu-only-multi-expert-canonical"


class CpuOnlyBaselineEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = loads_document((EVIDENCE / "baseline-report.json").read_text())

    def test_report_is_strict_constrained_cpu_baseline(self):
        report = self.report
        self.assertIsInstance(report, CpuOnlyBaselineReport)
        self.assertEqual(report.cpu_only_environment, CPU_ONLY_ENVIRONMENT)
        self.assertLess(report.service_memory_peak_bytes, report.service_memory_limit_bytes)
        self.assertEqual(report.service_swap_peak_bytes, 0)
        self.assertEqual(report.oom_kill_count, 0)
        self.assertEqual(report.service_final_state, "inactive")

    def test_two_experts_were_simultaneously_cpu_resident(self):
        report = self.report
        self.assertEqual(
            set(report.maximum_concurrent_loaded_model_refs),
            {"llama3.2:3b", "qwen2.5-coder:7b"},
        )
        executed = [item for item in report.attempts if item.inference_executed]
        self.assertEqual(len(executed), 2)
        self.assertTrue(all(item.provider_accelerator_bytes == 0 for item in executed))
        self.assertTrue(all(item.output_sha256 for item in executed))

    def test_strong_models_are_policy_rejections_not_substitutions(self):
        by_model = {item.model_ref: item for item in self.report.attempts}
        for model in ("laguna-xs.2:q4_K_M", "gemma4:26b"):
            attempt = by_model[model]
            self.assertEqual(attempt.decision.status, AdmissionStatus.REJECTED)
            self.assertFalse(attempt.inference_executed)
            self.assertEqual(
                attempt.decision.reason_codes[0],
                "memory.insufficient_after_safe_eviction",
            )

    def test_observations_are_linked_authoritative_and_inside_scheduler_limit(self):
        observations = self.report.observations
        self.assertEqual(len(observations), 7)
        self.assertTrue(all(item.memory.scope_authoritative for item in observations))
        self.assertTrue(all(
            item.memory.current_bytes <= item.memory.scheduler_limit_bytes
            for item in observations
        ))
        self.assertTrue(all(
            not accelerator.placement_allowed
            for item in observations for accelerator in item.accelerators
        ))

    def test_summary_matches_strict_report(self):
        summary = json.loads((EVIDENCE / "summary.json").read_text())
        self.assertEqual(summary["memory_peak_bytes"], self.report.service_memory_peak_bytes)
        self.assertEqual(summary["cpu_usage_microseconds"], self.report.service_cpu_usage_microseconds)
        self.assertEqual(summary["maximum_concurrent_loaded_model_refs"], list(self.report.maximum_concurrent_loaded_model_refs))


if __name__ == "__main__":
    unittest.main()
