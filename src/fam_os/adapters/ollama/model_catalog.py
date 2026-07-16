"""Strict observations of already installed Ollama model artifacts."""

from __future__ import annotations

from fam_os.adapters.ollama.errors import OllamaProtocolError
from fam_os.adapters.ollama.settings import OllamaSettings
from fam_os.adapters.ollama.transport import JsonObject, JsonTransport, UrllibJsonTransport
from fam_os.registry import ArtifactDigest
from fam_os.registry.runtime_artifacts import RuntimeArtifactObservation


class OllamaModelCatalog:
    def __init__(self, settings: OllamaSettings, transport: JsonTransport | None = None) -> None:
        self._settings = settings
        self._transport = transport or UrllibJsonTransport()

    def observe(self, artifact_ref: str) -> RuntimeArtifactObservation:
        if not artifact_ref.strip():
            raise ValueError("Ollama model reference must not be empty")
        payload = self._transport.request(
            "GET", self._settings.endpoint("/api/tags"), None,
            self._settings.timeout_seconds,
        )
        return parse_model_observation(payload, artifact_ref)


def parse_model_observation(payload: JsonObject, model_ref: str) -> RuntimeArtifactObservation:
    models = payload.get("models")
    if not isinstance(models, list):
        raise OllamaProtocolError("Ollama tags response requires models list")
    matches = tuple(item for item in models if _model_name(item) == model_ref)
    if len(matches) != 1:
        raise FileNotFoundError("exact Ollama model reference is not installed")
    value = matches[0]
    digest = value.get("digest")
    size = value.get("size")
    if not isinstance(digest, str) or not isinstance(size, int) or isinstance(size, bool):
        raise OllamaProtocolError("Ollama model requires digest and integer size")
    try:
        observed_digest = ArtifactDigest("sha256", digest)
    except ValueError as error:
        raise OllamaProtocolError("Ollama model digest is invalid") from error
    return RuntimeArtifactObservation(model_ref, observed_digest, size)


def _model_name(value: object) -> str | None:
    if not isinstance(value, dict):
        raise OllamaProtocolError("Ollama model entry must be an object")
    name = value.get("name") or value.get("model")
    if name is not None and not isinstance(name, str):
        raise OllamaProtocolError("Ollama model name must be a string")
    return name
