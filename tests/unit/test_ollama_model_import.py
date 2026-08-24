import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from fam_os.product.composition.ollama_model_import import OllamaModelStoreImporter


class OllamaModelStoreImporterTests(unittest.TestCase):
    def test_import_links_only_manifest_declared_digest_verified_blobs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, target = root / "source", root / "target"
            first = _blob(source, b"config")
            second = _blob(source, b"weights")
            manifest = source / "manifests/registry.ollama.ai/library/qwen3/1.7b"
            manifest.parent.mkdir(parents=True)
            manifest.write_text(json.dumps({
                "config": {"digest": first},
                "layers": [{"digest": second}],
            }))
            result = OllamaModelStoreImporter(source, target).import_model("qwen3:1.7b")
            self.assertEqual(2, result.blob_count)
            imported = target / "blobs" / second.replace(":", "-")
            original = source / "blobs" / second.replace(":", "-")
            self.assertEqual(original.stat().st_ino, imported.stat().st_ino)
            self.assertTrue((target / result.manifest_path).is_file())

    def test_digest_mismatch_is_rejected_before_link(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            blob = source / "blobs" / f"sha256-{'0' * 64}"
            blob.parent.mkdir(parents=True)
            blob.write_bytes(b"wrong")
            manifest = source / "manifests/registry.ollama.ai/library/model/latest"
            manifest.parent.mkdir(parents=True)
            manifest.write_text(json.dumps({
                "config": {"digest": "sha256:" + "0" * 64}, "layers": [],
            }))
            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                OllamaModelStoreImporter(source, root / "target").import_model("model")


def _blob(root: Path, content: bytes) -> str:
    digest = hashlib.sha256(content).hexdigest()
    path = root / "blobs" / f"sha256-{digest}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return f"sha256:{digest}"


if __name__ == "__main__":
    unittest.main()
