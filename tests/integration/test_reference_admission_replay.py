import json
import unittest
from pathlib import Path

from fam_os.scheduler.admission_contracts import AdmissionDecision, AdmissionRequest
from fam_os.schemas import loads_document


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs/admission/reference-weight-estimates.json"
EVIDENCE = ROOT / "artifacts/scheduler/phase7.4/reference-admission-replay"


class ReferenceAdmissionReplayTests(unittest.TestCase):
    def test_weight_estimates_are_context_free_artifact_bounds(self):
        config = json.loads(CONFIG.read_text())
        self.assertEqual(len(config["entries"]), 5)
        for entry in config["entries"]:
            expected = (entry["storage_bytes"] * 11 + 9) // 10
            self.assertEqual(entry["resident_weight_bytes"], expected)

    def test_every_replay_document_strictly_decodes(self):
        requests = sorted(EVIDENCE.glob("*.request.json"))
        decisions = sorted(EVIDENCE.glob("*.decision.json"))
        self.assertEqual(len(requests), 10)
        self.assertEqual(len(decisions), 10)
        self.assertTrue(all(isinstance(loads_document(path.read_text()), AdmissionRequest) for path in requests))
        self.assertTrue(all(isinstance(loads_document(path.read_text()), AdmissionDecision) for path in decisions))

    def test_full_profile_admits_strong_models_but_compat_rejects_them(self):
        summary = json.loads((EVIDENCE / "summary.json").read_text())
        by_key = {(item["profile"], item["model_ref"]): item for item in summary["profiles"]}
        for model in ("laguna-xs.2:q4_K_M", "gemma4:26b"):
            self.assertEqual(by_key[("full", model)]["status"], "admitted")
            self.assertEqual(by_key[("compat", model)]["status"], "rejected")


if __name__ == "__main__":
    unittest.main()
