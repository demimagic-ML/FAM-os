import json
import unittest
from pathlib import Path

from fam_os.experts.retrieval_evidence import RetrievalTierEvidence

ROOT = Path(__file__).parents[2]


class RetrievalTierEvidenceTests(unittest.TestCase):
    def test_live_evidence_proves_all_tiers_and_verified_release(self):
        raw = json.loads((
            ROOT / "artifacts/expert_fabric/phase9.4/retrieval-tiers-workstation.json"
        ).read_text())
        evidence = RetrievalTierEvidence(**{
            key: tuple(value) if isinstance(value, list) else value
            for key, value in raw.items()
        })

        self.assertTrue(evidence.released)
        self.assertEqual(768, evidence.embedding_dimension)
        self.assertEqual("hardware", evidence.ranked_source_ids[0])
        self.assertEqual(("hardware",), evidence.cited_source_ids)
        self.assertEqual(("claim-1",), evidence.verified_claim_ids)
        self.assertEqual(
            "0a109f422b47e3a30ba2b10eca18548e944e8a23073ee3f3e947efcf3c45e59f",
            evidence.embedding_artifact_sha256,
        )
        self.assertEqual(
            "a80c4f17acd55265feec403c7aef86be0c25983ab279d83f3bcd3abbcb5b8b72",
            evidence.synthesis_artifact_sha256,
        )


if __name__ == "__main__":
    unittest.main()
