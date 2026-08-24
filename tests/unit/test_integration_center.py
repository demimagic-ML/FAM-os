import os
import json
import tempfile
import unittest
from unittest.mock import patch
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

    def test_filesystem_configuration_is_written_and_reloaded(self) -> None:
        class Clients:
            def __init__(self): self.paths = []
            def reload_from_file(self, path): self.paths.append(path)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database = ProductionDatabase(StorageSettings(root / "fam.sqlite3", os.geteuid()))
            database.open()
            clients = Clients()
            with patch("fam_os.product.integration_center.shutil.which", return_value="/usr/bin/npx"):
                result = IntegrationCenter(database, state_root=root, mcp_clients=clients).configure(
                    "mcp.filesystem", {"configuration": {"roots": [temporary]}},
                )
            self.assertEqual("ready", result["status"])
            config = root / "config/mcp-clients.json"
            self.assertEqual(1, len(clients.paths))
            self.assertEqual(0, config.stat().st_mode & 0o077)
            document = json.loads(config.read_text())
            self.assertEqual("filesystem", document["servers"][0]["server_id"])
            database.close()


if __name__ == "__main__":
    unittest.main()
