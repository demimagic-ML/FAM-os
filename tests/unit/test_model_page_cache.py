import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from fam_os.adapters.linux.model_cache import (
    MmapPageCacheObserver,
    OllamaModelBlobResolver,
)


class ModelPageCacheTests(unittest.TestCase):
    def test_resolves_manifest_blob_without_exposing_or_mutating_content(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            content = b"model-weights" * 4096
            digest = hashlib.sha256(content).hexdigest()
            blob = root / "blobs" / f"sha256-{digest}"
            blob.parent.mkdir()
            blob.write_bytes(content)
            manifest = root / "manifests/registry.ollama.ai/library/test/1b"
            manifest.parent.mkdir(parents=True)
            manifest.write_text(json.dumps({"layers": [{
                "mediaType": "application/vnd.ollama.image.model",
                "digest": f"sha256:{digest}", "size": len(content),
            }]}))
            resolved = OllamaModelBlobResolver(root).resolve("test:1b")
            self.assertEqual(resolved.digest_sha256, digest)
            self.assertEqual(resolved.declared_bytes, len(content))
            self.assertEqual(blob.read_bytes(), content)

    def test_observes_and_safely_advises_cache_eviction(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            content = b"x" * (2 * 1024**2)
            digest = hashlib.sha256(content).hexdigest()
            path = root / f"sha256-{digest}"
            path.write_bytes(content)
            from fam_os.adapters.linux.model_cache import ResolvedModelBlob
            blob = ResolvedModelBlob("artifact-1", "test:1b", digest, len(content), path)
            observer = MmapPageCacheObserver(root)
            before = observer.observe(blob, "before")
            observer.evict(blob)
            after = observer.observe(blob, "after")
            self.assertEqual(after.file_bytes, len(content))
            self.assertLessEqual(after.resident_page_count, before.resident_page_count)
            self.assertEqual(path.read_bytes(), content)

    def test_rejects_traversal_and_symlink_blob(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, "references"):
                OllamaModelBlobResolver(root).resolve("../escape:latest")


if __name__ == "__main__":
    unittest.main()
