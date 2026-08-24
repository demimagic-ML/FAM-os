import os
import tempfile
import unittest
from pathlib import Path

from fam_os.product.integration_center import IntegrationCenter
from fam_os.product.storage.database import ProductionDatabase, StorageSettings


class IntegrationCenterTests(unittest.TestCase):
    def test_catalog_configure_and_retest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database = ProductionDatabase(StorageSettings(
                Path(temporary) / "fam.sqlite3", os.geteuid(),
            ))
            database.open()
            center = IntegrationCenter(database)
            catalog = center.catalog()["integrations"]
            self.assertEqual(8, len(catalog))
            configured = center.configure("mcp.filesystem", {
                "enabled": True, "configuration": {"roots": [temporary]},
            })
            self.assertTrue(configured["enabled"])
            self.assertIn(configured["status"], {"ready", "missing_runtime"})
            self.assertEqual(configured["status"], center.test("mcp.filesystem")["status"])
            self.assertTrue(center.catalog()["integrations"][0]["configured"])
            database.close()

    def test_unknown_catalog_entry_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database = ProductionDatabase(StorageSettings(
                Path(temporary) / "fam.sqlite3", os.geteuid(),
            ))
            database.open()
            with self.assertRaises(KeyError):
                IntegrationCenter(database).configure("unknown", {})
            database.close()


if __name__ == "__main__":
    unittest.main()
