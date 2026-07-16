import json
import os
import unittest
from pathlib import Path

from fam_os.experts import ExpertRuntimeBinding
from fam_os.scheduler import ExpertResidencyCatalog
from fam_os.schemas import loads_document


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "artifacts/scheduler/phase7.3/qwen-residency-lifecycle-canonical"


class ResidencyLifecycleEvidenceTests(unittest.TestCase):
    def test_live_sequence_is_revision_linked_and_provider_confirmed(self):
        summary = json.loads((EVIDENCE / "summary.json").read_text())
        self.assertEqual(
            summary["states"],
            ["cold", "warm", "active", "warm", "evicting", "cold"],
        )
        self.assertEqual(summary["revisions"], list(range(6)))
        self.assertTrue(summary["provider_absent_before_cold"])
        self.assertEqual(summary["final_file_revision"], 5)
        self.assertEqual(summary["service_final_state"], "inactive")
        self.assertGreater(summary["service_cpu_usage_microseconds"], 0)
        self.assertGreater(summary["service_memory_peak_bytes"], 0)

    def test_every_snapshot_is_strict_and_matches_current_runtime_binding(self):
        binding = loads_document((
            ROOT / "configs/packages/bindings/code-qwen2.5-coder-7b.json"
        ).read_text())
        self.assertIsInstance(binding, ExpertRuntimeBinding)
        names = ("cold", "warm", "active", "warm-released", "evicting", "cold-confirmed")
        catalogs = [loads_document((EVIDENCE / f"{name}.json").read_text()) for name in names]
        self.assertTrue(all(isinstance(item, ExpertResidencyCatalog) for item in catalogs))
        identities = [item.records[0].identity.runtime_artifact_id for item in catalogs]
        self.assertEqual(set(identities), {binding.artifact_ref})

        final_path = EVIDENCE / "residency-state.json"
        final = loads_document(final_path.read_text())
        self.assertEqual(final, catalogs[-1])
        self.assertEqual(os.stat(final_path).st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
