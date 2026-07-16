import json
import unittest
from pathlib import Path

from fam_os.experts.media_evidence import MediaExpertEvidence

ROOT = Path(__file__).parents[2]


class MediaExpertEvidenceTests(unittest.TestCase):
    def test_live_workstation_evidence_covers_all_four_capabilities(self):
        raw = json.loads((
            ROOT / "artifacts/expert_fabric/phase9.6/media-expert-workstation.json"
        ).read_text())
        evidence = MediaExpertEvidence(**raw)
        self.assertTrue(evidence.passed)
        self.assertEqual("FAM LOCAL 5080", evidence.ocr_observed_text)
        self.assertIn("FAM LOCAL 5080", evidence.vision_description)
        self.assertEqual(evidence.asr_expected_text, evidence.asr_observed_text)
        self.assertEqual("qwen3-vl:8b", evidence.vision_model_ref)
        self.assertEqual("tiny.en", evidence.asr_model_ref)


if __name__ == "__main__":
    unittest.main()
