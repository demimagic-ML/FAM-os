"""Provider-specific failures translated at the Ollama boundary."""


class OllamaError(RuntimeError):
    """Base failure raised by the Ollama adapter."""


class OllamaTransportError(OllamaError):
    """The runtime could not be reached or returned invalid HTTP data."""


class OllamaProtocolError(OllamaError):
    """The runtime returned JSON that violates the expected provider shape."""

