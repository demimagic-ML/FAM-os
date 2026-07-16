import json
import unittest
from pathlib import Path

from fam_os.experts import ExpertManifest, ExpertRuntimeBinding
from fam_os.schemas import loads_document


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs/context_profiles/reference-models.json"
MANIFESTS = ROOT / "configs/packages/experts"
BINDINGS = ROOT / "configs/packages/bindings"


CURRENT_FILES = {
    "expert.language.llama3.2-3b": (
        "language-llama3.2-3b.json", "language-llama3.2-3b.json"
    ),
    "expert.code.qwen2.5-coder-7b": (
        "code-qwen2.5-coder-7b.json", "code-qwen2.5-coder-7b.json"
    ),
    "expert.retrieval.nomic-embed-text": (
        "retrieval-nomic-embed-text.json", "retrieval-nomic-embed-text.json"
    ),
    "expert.code.laguna-xs2-33b": (
        "code-laguna-xs2-33b-1.0.2.json", "code-laguna-xs2-33b-1.0.2.json"
    ),
    "expert.code.gemma4-26b": (
        "code-gemma4-26b-1.0.2.json", "code-gemma4-26b-1.0.2.json"
    ),
}


class ReferenceContextProfileTests(unittest.TestCase):
    def test_every_current_package_has_exact_binding_capacity_and_strategy(self):
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
        entries = {item["expert_id"]: item for item in config["entries"]}
        self.assertEqual(set(entries), set(CURRENT_FILES))

        for expert_id, (manifest_name, binding_name) in CURRENT_FILES.items():
            with self.subTest(expert_id=expert_id):
                manifest = loads_document((MANIFESTS / manifest_name).read_text())
                binding = loads_document((BINDINGS / binding_name).read_text())
                self.assertIsInstance(manifest, ExpertManifest)
                self.assertIsInstance(binding, ExpertRuntimeBinding)
                entry = entries[expert_id]
                self.assertEqual(entry["model_ref"], binding.artifact_ref)
                self.assertEqual(
                    entry["maximum_context_tokens"], manifest.resources.max_context_tokens
                )
                expected = (
                    "encoder_activation_bound"
                    if binding.runtime_contract_id == "fam.embedding.text/v1"
                    else "autoregressive_kv"
                )
                self.assertEqual(entry["strategy"], expected)

    def test_live_evidence_includes_both_strong_models_and_excludes_weights(self):
        path = ROOT / "artifacts/scheduler/phase7.2/reference-context-estimates/summary.json"
        report = json.loads(path.read_text(encoding="utf-8"))
        by_model = {item["model_ref"]: item for item in report["profiles"]}

        self.assertIn("laguna-xs.2:q4_K_M", by_model)
        self.assertIn("gemma4:26b", by_model)
        self.assertTrue(all(item["model_resident_bytes_excluded"] for item in by_model.values()))
        self.assertTrue(all(item["total_context_bytes"] > 0 for item in by_model.values()))


if __name__ == "__main__":
    unittest.main()
