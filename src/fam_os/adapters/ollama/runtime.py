"""Ollama implementation of provider-neutral inference lifecycle operations."""

from __future__ import annotations

import time
from collections.abc import Callable

from fam_os.adapters.ollama.errors import OllamaTransportError
from fam_os.adapters.ollama.payloads import build_chat_payload, build_unload_payload
from fam_os.adapters.ollama.responses import parse_chat_response, parse_loaded_models
from fam_os.adapters.ollama.settings import OllamaSettings
from fam_os.adapters.ollama.transport import JsonTransport, UrllibJsonTransport
from fam_os.core.ports.inference import InferenceRequest, InferenceResponse, LoadedModel


class OllamaRuntime:
    def __init__(
        self,
        settings: OllamaSettings,
        transport: JsonTransport | None = None,
        clock: Callable[[], float] | None = None,
        sleeper: Callable[[float], None] | None = None,
    ) -> None:
        self._settings = settings
        self._transport = transport or UrllibJsonTransport()
        self._clock = clock or time.perf_counter
        self._sleep = sleeper or time.sleep

    def chat(self, request: InferenceRequest) -> InferenceResponse:
        started = self._clock()
        payload = self._transport.request(
            "POST",
            self._settings.endpoint("/api/chat"),
            build_chat_payload(request),
            self._settings.timeout_seconds,
        )
        return parse_chat_response(request.model_ref, payload, self._clock() - started)

    def unload(self, model_ref: str) -> None:
        self._transport.request(
            "POST",
            self._settings.endpoint("/api/generate"),
            build_unload_payload(model_ref),
            self._settings.timeout_seconds,
        )
        self._wait_until_unloaded(model_ref)

    def loaded_models(self) -> tuple[LoadedModel, ...]:
        payload = self._transport.request(
            "GET",
            self._settings.endpoint("/api/ps"),
            None,
            self._settings.timeout_seconds,
        )
        return parse_loaded_models(payload)

    def _wait_until_unloaded(self, model_ref: str) -> None:
        deadline = self._clock() + self._settings.unload_timeout_seconds
        while any(model.model_ref == model_ref for model in self.loaded_models()):
            if self._clock() >= deadline:
                raise OllamaTransportError(
                    f"model remained loaded after unload request: {model_ref}"
                )
            self._sleep(self._settings.unload_poll_seconds)
