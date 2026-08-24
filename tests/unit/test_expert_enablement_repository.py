import os
import tempfile
import unittest
from pathlib import Path

from fam_os.core.production import ModelIntent, RuntimeModelEntry
from fam_os.core.production.model_catalog import RuntimeModelProvenance
from fam_os.core.production.model_catalog import RuntimeModelCatalog
from fam_os.product.composition.core_storage import CoreStorageComposition
from fam_os.product.storage import (
    OwnerKeyStore,
    ProductionDatabase,
    SecureStorage,
    StorageSettings,
)


class ExpertEnablementRepositoryTests(unittest.TestCase):
    def test_signed_catalog_sync_preserves_explicit_disable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database = ProductionDatabase(StorageSettings(root / "fam.sqlite3", os.geteuid()))
            opened = SecureStorage(
                database, OwnerKeyStore(root / "master.key", os.geteuid()),
            ).open()
            repository = CoreStorageComposition(
                database, opened.cipher, str(os.geteuid()),
            ).repositories().expert_enablement
            model = RuntimeModelEntry(
                "qwen3:1.7b", "economical", (ModelIntent.CONVERSATION,),
                1024**3, 8192, "a" * 64,
            )
            provenance = RuntimeModelProvenance(
                "qwen3:1.7b", "expert.language.qwen3-1.7b",
                "fam.expert.language.qwen3-1.7b@1.0.0",
                "ollama.local/v1:ollama.model",
                model.intents, model.verifier_ids,
            )
            repository.synchronize(provenance, model)
            self.assertEqual({provenance.expert_id}, repository.enabled_expert_ids())
            self.assertEqual(((provenance, model),), repository.enabled_models())
            catalog = RuntimeModelCatalog(())
            catalog.install_runtime_model(model, provenance)
            self.assertEqual(model, catalog.get(model.model_ref))
            self.assertTrue(repository.set_enabled(provenance.expert_id, False))
            repository.synchronize(provenance, model)
            self.assertEqual(set(), repository.enabled_expert_ids())
            self.assertEqual((), repository.enabled_models())
            database.close()


if __name__ == "__main__":
    unittest.main()
