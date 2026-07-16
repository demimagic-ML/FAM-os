import json
import unittest
from pathlib import Path

from fam_os.scheduler import FullWorkstationGpuReport, GpuPlacementEvidence
from fam_os.schemas import loads_document


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "artifacts/scheduler/phase7.6/full-gpu-placement-canonical"


class FullGpuPlacementEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = loads_document((EVIDENCE / "gpu-report.json").read_text())

    def test_report_is_strict_full_workstation_evidence(self):
        report = self.report
        self.assertIsInstance(report, FullWorkstationGpuReport)
        self.assertEqual(report.validation_profile_id, "full-reference-workstation")
        self.assertEqual(report.service_final_state, "inactive")
        self.assertEqual(report.final_loaded_model_refs, ())
        self.assertGreater(report.service_cpu_usage_microseconds, 0)
        self.assertGreater(report.service_memory_peak_bytes, 16 * 1024**3)

    def test_every_model_has_linked_observed_gpu_placement(self):
        self.assertEqual(len(self.report.evidences), 4)
        for item in self.report.evidences:
            with self.subTest(model=item.request.weight.runtime_artifact_id):
                self.assertIsInstance(item, GpuPlacementEvidence)
                self.assertGreater(item.provider_accelerator_bytes, 0)
                self.assertLessEqual(
                    item.provider_accelerator_bytes,
                    item.decision.accelerator_reservation_bytes,
                )
                self.assertGreater(item.accelerator_memory_delta_bytes, 0)
                self.assertEqual(
                    item.after_load_observation.previous_observation_id,
                    item.request.observation.observation_id,
                )

    def test_strong_models_are_real_split_offloads(self):
        by_model = {
            item.request.weight.runtime_artifact_id: item
            for item in self.report.evidences
        }
        expected = {
            "laguna-xs.2:q4_K_M": (16, 40),
            "gemma4:26b": (8, 30),
        }
        for model, layers in expected.items():
            item = by_model[model]
            self.assertEqual(
                (item.request.requested_accelerator_layers, item.request.model_layer_count),
                layers,
            )
            self.assertGreater(item.provider_host_compute_bytes, 0)
            self.assertGreater(item.provider_accelerator_bytes, 0)

    def test_transfer_cost_uses_disclosed_provider_load_duration(self):
        for item in self.report.evidences:
            self.assertTrue(item.transfer_duration_includes_provider_load_overhead)
            self.assertAlmostEqual(
                item.effective_transfer_bytes_per_second,
                item.provider_accelerator_bytes / item.provider_load_seconds,
                places=6,
            )

    def test_summary_matches_strict_report(self):
        summary = json.loads((EVIDENCE / "summary.json").read_text())
        self.assertEqual(len(summary["placements"]), len(self.report.evidences))
        self.assertEqual(
            summary["service_memory_peak_bytes"],
            self.report.service_memory_peak_bytes,
        )


if __name__ == "__main__":
    unittest.main()
