"""Ollama implementation of the inference-runtime port."""

from fam_os.adapters.ollama.errors import OllamaProtocolError, OllamaTransportError
from fam_os.adapters.ollama.runtime import OllamaRuntime
from fam_os.adapters.ollama.artifact_store import OllamaModelArtifactStore
from fam_os.adapters.ollama.model_catalog import OllamaModelCatalog
from fam_os.adapters.ollama.settings import OllamaSettings
from fam_os.adapters.ollama.context_profile import (
    OllamaContextProfileObserver,
    OllamaContextProfilePolicy,
    parse_ollama_context_profile,
)

__all__ = [
    "OllamaModelArtifactStore",
    "OllamaModelCatalog",
    "OllamaProtocolError",
    "OllamaRuntime",
    "OllamaSettings",
    "OllamaTransportError",
    "OllamaContextProfileObserver",
    "OllamaContextProfilePolicy",
    "parse_ollama_context_profile",
]
