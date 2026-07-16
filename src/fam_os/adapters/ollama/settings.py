"""Validated adapter configuration supplied by the composition root."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class OllamaSettings:
    base_url: str
    timeout_seconds: float
    unload_timeout_seconds: float = 10.0
    unload_poll_seconds: float = 0.05

    def __post_init__(self) -> None:
        normalized = self.base_url.rstrip("/")
        if not normalized.startswith(("http://", "https://")):
            raise ValueError("base_url must use http or https")
        timeouts = (
            self.timeout_seconds,
            self.unload_timeout_seconds,
            self.unload_poll_seconds,
        )
        if any(value <= 0 for value in timeouts):
            raise ValueError("Ollama timeouts must be positive")
        object.__setattr__(self, "base_url", normalized)

    def endpoint(self, path: str) -> str:
        if not path.startswith("/"):
            raise ValueError("endpoint path must begin with a slash")
        return f"{self.base_url}{path}"
