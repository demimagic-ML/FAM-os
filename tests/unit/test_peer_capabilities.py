import tempfile
import unittest
from pathlib import Path

from fam_os.core.production import ModelIntent, RuntimeModelEntry
from fam_os.core.production.model_catalog import (
    RuntimeModelCatalog,
    RuntimeModelProvenance,
)
from fam_os.product.peer_capabilities import catalog_capability_source
from tests.unit.test_remote_context import NOW, _credentials


class PeerCatalogCapabilityTests(unittest.TestCase):
    def test_shared_model_advertises_each_enabled_expert_scope(self) -> None:
        entry = RuntimeModelEntry(
            "llama3.2:3b", "economical",
            (ModelIntent.CONVERSATION, ModelIntent.MATH, ModelIntent.RETRIEVAL),
            2 * 1024**3, 8192, "a" * 64,
            (
                "verifier.text.exact-v1",
                "math.sympy-equivalence.v1",
                "retrieval.citations.v1",
            ),
        )
        provenances = (
            RuntimeModelProvenance(
                entry.model_ref, "expert.language", "language@1.0.0", "binding:1",
                (ModelIntent.CONVERSATION,), ("verifier.text.exact-v1",),
            ),
            RuntimeModelProvenance(
                entry.model_ref, "expert.math", "math@1.0.0", "binding:2",
                (ModelIntent.MATH,), ("math.sympy-equivalence.v1",),
            ),
            RuntimeModelProvenance(
                entry.model_ref, "expert.retrieval", "retrieval@1.0.0", "binding:3",
                (ModelIntent.RETRIEVAL,), ("retrieval.citations.v1",),
            ),
        )
        catalog = RuntimeModelCatalog((entry,), provenances)

        with tempfile.TemporaryDirectory() as temporary:
            credentials = _credentials(Path(temporary), "Shared model peer")
            declarations = catalog_capability_source(catalog)(credentials, NOW)

        self.assertEqual(3, len(declarations))
        self.assertEqual(
            {
                "expert.language": ("language.generate",),
                "expert.math": ("math.solve",),
                "expert.retrieval": ("retrieval.query",),
            },
            {item.expert_id: item.capability_ids for item in declarations},
        )
        self.assertEqual({entry.model_ref}, {item.model_ref for item in declarations})


if __name__ == "__main__":
    unittest.main()
