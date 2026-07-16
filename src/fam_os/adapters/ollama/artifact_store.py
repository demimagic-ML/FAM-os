"""Lifecycle artifact store for externally owned installed Ollama models."""

from __future__ import annotations

from fam_os.experts.registry_contracts import ExpertPackageCoordinate
from fam_os.registry.package import ArtifactDigest
from fam_os.registry.runtime_artifacts import RuntimeArtifactCatalog


_PREFIX = "ollama-model:"


class OllamaModelArtifactStore:
    def __init__(self, catalog: RuntimeArtifactCatalog) -> None:
        self._catalog = catalog

    def install(
        self,
        coordinate: ExpertPackageCoordinate,
        source_locator: str,
        expected_digest: ArtifactDigest,
    ) -> str:
        del coordinate
        self._verify_ref(source_locator, expected_digest)
        return _PREFIX + source_locator

    def verify(self, artifact_locator: str, expected_digest: ArtifactDigest) -> None:
        if not artifact_locator.startswith(_PREFIX):
            raise ValueError("artifact locator is not an Ollama model")
        self._verify_ref(artifact_locator.removeprefix(_PREFIX), expected_digest)

    def remove(self, artifact_locator: str) -> None:
        if not artifact_locator.startswith(_PREFIX):
            raise ValueError("artifact locator is not an Ollama model")
        # Package removal never deletes a user-owned downloaded model.

    def _verify_ref(self, model_ref: str, expected_digest: ArtifactDigest) -> None:
        observed = self._catalog.observe(model_ref)
        if observed.digest != expected_digest:
            raise ValueError("installed Ollama model digest does not match package evidence")
