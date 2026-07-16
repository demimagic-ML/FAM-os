import json
import unittest
from pathlib import Path

from fam_os.memory.document_contracts import DocumentIndexEvidence

ROOT = Path(__file__).parents[2]


class DocumentIndexEvidenceTests(unittest.TestCase):
    def test_live_nomic_index_is_approved_digest_bound_and_scope_denied(self):
        raw = json.loads((
            ROOT / "artifacts/memory/phase10.3/document-index-evidence.json"
        ).read_text())
        evidence = DocumentIndexEvidence(**raw)
        self.assertTrue(evidence.passed)
        self.assertEqual(2, evidence.indexed_chunk_count)
        self.assertEqual(0, evidence.denied_scope_hit_count)
        self.assertEqual("fam-overview:chunk:0", evidence.top_chunk_id)
        self.assertEqual("nomic-embed-text:latest", evidence.embedding_model_ref)


if __name__ == "__main__":
    unittest.main()
