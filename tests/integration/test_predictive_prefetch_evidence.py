import hashlib
import json
import unittest
from pathlib import Path

from fam_os.scheduler import (
    PredictivePrefetchReport,
    PrefetchAdmissionStatus,
)
from fam_os.schemas import loads_document


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "artifacts/scheduler/phase7.10/qwen-predictive-prefetch-canonical"
CPU = ROOT / "artifacts/scheduler/phase7.5/cpu-only-multi-expert-canonical/baseline-report.json"
GPU = ROOT / "artifacts/scheduler/phase7.6/full-gpu-placement-canonical/gpu-report.json"


class PredictivePrefetchEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = loads_document(
            (EVIDENCE / "predictive-prefetch-report.json").read_text(encoding="utf-8")
        )

    def test_prediction_has_two_digest_bound_supporting_transitions(self):
        report = self.report
        self.assertIsInstance(report, PredictivePrefetchReport)
        self.assertEqual(report.prediction.transition_observations, 2)
        self.assertEqual(report.prediction.confidence, 1.0)
        sources = {item.sequence_id: item for item in report.prediction_request.history}
        self.assertEqual(sources["cpu-baseline"].source_evidence_digest_sha256, _digest(CPU))
        self.assertEqual(sources["gpu-placement"].source_evidence_digest_sha256, _digest(GPU))

    def test_admission_is_byte_io_concurrency_waste_and_reserve_bounded(self):
        request = self.report.admitted_request
        decision = self.report.admitted_decision
        self.assertEqual(decision.status, PrefetchAdmissionStatus.ADMITTED)
        self.assertEqual(decision.reserved_prefetch_bytes, 32 * 1024**2)
        self.assertEqual(decision.reserved_io_read_bytes, 32 * 1024**2)
        self.assertEqual(request.budget.operating_system_reserve_bytes, 12 * 1024**3)
        self.assertEqual(request.budget.maximum_concurrent_prefetches, 1)
        self.assertFalse(request.eviction_permitted)
        self.assertEqual(decision.selected_eviction_artifact_ids, ())

    def test_live_prefetch_warms_exact_range_and_demand_reads_no_disk(self):
        execution = self.report.execution
        self.assertEqual(execution.prefetched_bytes, 32 * 1024**2)
        self.assertEqual(execution.demand_read_bytes, 32 * 1024**2)
        self.assertGreaterEqual(execution.prefetch_physical_read_bytes, execution.prefetched_bytes)
        self.assertEqual(execution.demand_physical_read_bytes, 0)
        self.assertGreaterEqual(
            execution.cache_bytes_after - execution.cache_bytes_before,
            execution.prefetched_bytes,
        )
        self.assertEqual(execution.prefetch_digest_sha256, execution.demand_digest_sha256)

    def test_waste_ceiling_rejects_second_speculation(self):
        decision = self.report.waste_guard_decision
        self.assertEqual(decision.status, PrefetchAdmissionStatus.REJECTED)
        self.assertEqual(decision.reasons, ("budget.maximum_waste_exceeded",))
        self.assertEqual(decision.reserved_prefetch_bytes, 0)

    def test_owned_clone_is_removed_and_summary_is_private(self):
        self.assertTrue(self.report.execution.temporary_artifact_removed)
        summary = json.loads((EVIDENCE / "summary.json").read_text(encoding="utf-8"))
        self.assertTrue(summary["temporary_artifact_removed"])
        self.assertNotIn("/tmp/", repr(summary))
        self.assertNotIn("/home/", repr(summary))


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    unittest.main()
