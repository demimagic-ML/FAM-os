import hashlib
import json
import unittest
from pathlib import Path

from fam_os.scheduler import NpuInvestigationOutcome, NpuInvestigationReport
from fam_os.schemas import loads_document


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "artifacts/scheduler/phase7.8/intel-npu-micro-expert-canonical"


class NpuInvestigationEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = loads_document(
            (EVIDENCE / "npu-investigation-report.json").read_text(encoding="utf-8")
        )

    def test_real_arrow_lake_npu_and_kernel_driver_are_recorded(self):
        report = self.report
        self.assertIsInstance(report, NpuInvestigationReport)
        self.assertEqual(report.outcome, NpuInvestigationOutcome.SUPPORTED)
        self.assertEqual(report.hardware.vendor_id, "0x8086")
        self.assertEqual(report.hardware.device_id, "0xad1d")
        self.assertEqual(report.hardware.kernel_driver, "intel_vpu")
        self.assertTrue(report.hardware.device_node_present)

    def test_runtime_and_execution_are_npu_only_without_fallback(self):
        report = self.report
        self.assertIn("NPU", report.runtime.available_devices)
        self.assertEqual(report.runtime.execution_devices, ("NPU",))
        self.assertEqual(report.runtime.requested_device, "NPU")
        self.assertFalse(report.runtime.cpu_fallback_allowed)
        self.assertFalse(report.micro_expert.fallback_used)

    def test_micro_expert_classifies_and_runs_repeatedly(self):
        expert = self.report.micro_expert
        self.assertEqual(expert.expected_label, "code")
        self.assertEqual(expert.observed_label, "code")
        self.assertGreater(expert.compile_duration_ms, 0)
        self.assertGreater(expert.first_inference_duration_ms, 0)
        self.assertEqual(len(expert.warm_inference_durations_ms), 5)

    def test_serialized_model_digest_matches_evidence(self):
        digest = hashlib.sha256()
        digest.update((EVIDENCE / "routing-micro-expert.xml").read_bytes())
        digest.update((EVIDENCE / "routing-micro-expert.bin").read_bytes())
        self.assertEqual(digest.hexdigest(), self.report.micro_expert.model_digest_sha256)

    def test_summary_is_consistent_and_privacy_reviewed(self):
        summary = json.loads((EVIDENCE / "summary.json").read_text(encoding="utf-8"))
        self.assertEqual(summary["execution_devices"], ["NPU"])
        self.assertFalse(summary["fallback_used"])
        serialized = repr(summary)
        self.assertNotIn("/home/", serialized)
        self.assertNotIn("private-user", serialized)
        self.assertNotIn("00:0b.0", serialized)


if __name__ == "__main__":
    unittest.main()
