import os
import tempfile
import unittest
from pathlib import Path

from fam_os.adapters.filesystem import DirectoryExpertManifestSource
from fam_os.experts import LocalExpertRegistry
from fam_os.schemas import dumps_document
from tests.contract.schema_manifest_fixtures import legacy_expert_manifest
from tests.unit.test_package_expert_manifests import _manifest


class DirectoryExpertManifestRegistryTests(unittest.TestCase):
    def test_strict_current_documents_refresh_local_registry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            value = _manifest()
            (root / "code.json").write_text(dumps_document(value), encoding="utf-8")
            registry = LocalExpertRegistry()
            self.assertTrue(registry.refresh_from(DirectoryExpertManifestSource(root)))
            self.assertEqual(value, registry.lookup(value.package.package_id, "1.0.0"))

    def test_legacy_wrong_family_symlink_and_oversize_documents_fail_closed(self):
        cases = (
            ("legacy.json", dumps_document(legacy_expert_manifest()), {}),
            ("large.json", "x" * 20, {"maximum_document_bytes": 10}),
        )
        for filename, content, options in cases:
            with self.subTest(filename=filename), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / filename).write_text(content, encoding="utf-8")
                with self.assertRaises(ValueError):
                    DirectoryExpertManifestSource(root, **options).load()

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target"
            target.write_text(dumps_document(_manifest()), encoding="utf-8")
            os.symlink(target, root / "linked.json")
            with self.assertRaises(OSError):
                DirectoryExpertManifestSource(root).load()


if __name__ == "__main__":
    unittest.main()
