import unittest
from dataclasses import replace

from fam_os.adapters.ollama import (
    OllamaModelArtifactStore,
    OllamaModelCatalog,
    OllamaProtocolError,
    OllamaSettings,
)
from fam_os.experts import (
    ExpertPackageCoordinate,
    ExpertRuntimeBinding,
    validate_runtime_binding,
)
from fam_os.registry import ArtifactDigest
from tests.unit.test_package_expert_manifests import _manifest, _package


DIGEST = ArtifactDigest("sha256", "a" * 64)


class OllamaExpertPackageTests(unittest.TestCase):
    def test_catalog_observes_exact_installed_model_digest_and_size(self) -> None:
        transport = _Transport({"models": [
            {"name": "model:one", "digest": "a" * 64, "size": 123},
            {"name": "model:other", "digest": "b" * 64, "size": 456},
        ]})
        catalog = OllamaModelCatalog(OllamaSettings("http://local", 1), transport)
        observation = catalog.observe("model:one")
        self.assertEqual(DIGEST, observation.digest)
        self.assertEqual(123, observation.size_bytes)
        self.assertEqual(("GET", "http://local/api/tags", None, 1), transport.call)

    def test_catalog_fails_closed_on_missing_duplicate_or_malformed_models(self) -> None:
        settings = OllamaSettings("http://local", 1)
        with self.assertRaises(FileNotFoundError):
            OllamaModelCatalog(settings, _Transport({"models": []})).observe("missing")
        duplicate = {"models": [
            {"name": "same", "digest": "a" * 64, "size": 1},
            {"name": "same", "digest": "a" * 64, "size": 1},
        ]}
        with self.assertRaises(FileNotFoundError):
            OllamaModelCatalog(settings, _Transport(duplicate)).observe("same")
        with self.assertRaises(OllamaProtocolError):
            OllamaModelCatalog(settings, _Transport({"models": "wrong"})).observe("same")

    def test_external_artifact_store_verifies_but_never_deletes_user_model(self) -> None:
        catalog = _Catalog()
        store = OllamaModelArtifactStore(catalog)
        coordinate = ExpertPackageCoordinate("package.code", "1")
        locator = store.install(coordinate, "model:one", DIGEST)
        self.assertEqual("ollama-model:model:one", locator)
        store.verify(locator, DIGEST)
        store.remove(locator)
        self.assertEqual(["model:one", "model:one"], catalog.calls)
        with self.assertRaisesRegex(ValueError, "digest"):
            store.install(coordinate, "model:one", ArtifactDigest("sha256", "b" * 64))

    def test_runtime_binding_is_exact_manifest_artifact_and_digest(self) -> None:
        manifest = _manifest(
            package=_package(artifact_digest=DIGEST),
            artifact_ids=("ollama.model",),
        )
        binding = ExpertRuntimeBinding(
            ExpertPackageCoordinate(
                manifest.package.package_id, manifest.package.package_version
            ),
            manifest.expert_id,
            manifest.runtime_contract_id,
            "ollama.local/v1",
            "ollama.model",
            "model:one",
            DIGEST,
        )
        validate_runtime_binding(manifest, binding)
        with self.assertRaisesRegex(ValueError, "digest"):
            validate_runtime_binding(
                manifest,
                replace(binding, expected_artifact_digest=ArtifactDigest("sha256", "b" * 64)),
            )


class _Transport:
    def __init__(self, response):
        self.response = response
        self.call = None

    def request(self, method, url, payload, timeout_seconds):
        self.call = (method, url, payload, timeout_seconds)
        return self.response


class _Catalog:
    def __init__(self):
        self.calls = []

    def observe(self, artifact_ref):
        from fam_os.registry.runtime_artifacts import RuntimeArtifactObservation

        self.calls.append(artifact_ref)
        return RuntimeArtifactObservation(artifact_ref, DIGEST, 123)


if __name__ == "__main__":
    unittest.main()
