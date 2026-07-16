import json
import unittest
from pathlib import Path

from fam_os.scheduler import LoadCacheState, StoragePagingEvidence
from fam_os.schemas import loads_document


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "artifacts/scheduler/phase7.7/llama-storage-paging-canonical"


class StoragePagingEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evidence = loads_document(
            (EVIDENCE / "storage-paging-evidence.json").read_text()
        )

    def test_strict_artifact_is_nvme_private_and_not_ram(self):
        evidence = self.evidence
        self.assertIsInstance(evidence, StoragePagingEvidence)
        self.assertEqual(evidence.artifact.storage_medium.value, "nvme")
        self.assertFalse(evidence.artifact.path_disclosed)
        self.assertTrue(evidence.artifact.storage_bytes_excluded_from_ram_capacity)
        self.assertEqual(
            evidence.artifact.declared_bytes,
            evidence.artifact.observed_file_bytes,
        )

    def test_cold_eviction_and_full_repopulation_are_observed(self):
        evidence = self.evidence
        self.assertEqual(evidence.cold_trial.cache_state, LoadCacheState.COLD)
        self.assertGreater(evidence.cache_before_eviction.resident_fraction, 0.99)
        self.assertEqual(evidence.cold_trial.cache_before_load.resident_page_count, 0)
        self.assertGreater(evidence.cold_trial.cache_after_load.resident_fraction, 0.99)
        self.assertTrue(evidence.cold_trial.cache_eviction_effective)

    def test_physical_io_distinguishes_cold_from_warm_load(self):
        evidence = self.evidence
        self.assertGreaterEqual(
            evidence.cold_trial.physical_read_bytes,
            evidence.artifact.observed_file_bytes,
        )
        self.assertEqual(evidence.warm_trial.physical_read_bytes, 0)
        self.assertGreater(evidence.warm_trial.logical_read_bytes, 0)
        self.assertLess(
            evidence.warm_trial.provider_load_seconds,
            evidence.cold_trial.provider_load_seconds,
        )

    def test_budget_is_enforced_without_false_kernel_claim(self):
        budget = self.evidence.budget
        self.assertFalse(budget.kernel_bandwidth_controller_available)
        self.assertTrue(budget.cumulative_process_io_enforced)
        self.assertLessEqual(
            self.evidence.cold_trial.physical_read_bytes,
            budget.maximum_physical_read_bytes,
        )
        self.assertLessEqual(
            self.evidence.cold_trial.physical_write_bytes,
            budget.maximum_physical_write_bytes,
        )

    def test_cleanup_and_summary_are_consistent(self):
        evidence = self.evidence
        self.assertEqual(evidence.service_final_state, "inactive")
        self.assertEqual(evidence.final_loaded_model_refs, ())
        summary = json.loads((EVIDENCE / "summary.json").read_text())
        self.assertEqual(
            summary["cold_physical_read_bytes"],
            evidence.cold_trial.physical_read_bytes,
        )
        self.assertNotIn("/usr/share", repr(summary))
        self.assertNotIn("/tmp/", repr(summary))


if __name__ == "__main__":
    unittest.main()
