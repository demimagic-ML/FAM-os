"""Ollama implementation of provider-neutral inference lifecycle operations."""

from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import time
from collections.abc import Callable

from fam_os.adapters.ollama.errors import OllamaTransportError
from fam_os.adapters.ollama.payloads import (
    build_chat_payload,
    build_embedding_payload,
    build_prewarm_payload,
    build_unload_payload,
)
from fam_os.adapters.ollama.responses import parse_chat_response, parse_embedding_response, parse_loaded_models
from fam_os.adapters.ollama.settings import OllamaSettings
from fam_os.adapters.ollama.transport import JsonTransport, UrllibJsonTransport
from fam_os.core.ports.inference import (
    InferenceRequest, InferenceResponse, InferenceToolCall, LoadedModel,
)
from fam_os.adapters.ollama.errors import OllamaProtocolError
from fam_os.core.ports.embedding import EmbeddingRequest, EmbeddingResponse


_EMBEDDING_RESIDENCY_PROBE = "FAM_OS embedding residency probe"


class OllamaRuntime:
    supports_native_tools = True

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
        response = parse_chat_response(
            request.model_ref, payload, self._clock() - started,
        )
        return _recover_content_tool_call(request, response)

    def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        started = self._clock()
        payload = self._transport.request(
            "POST", self._settings.endpoint("/api/embed"),
            build_embedding_payload(request), self._settings.timeout_seconds,
        )
        return parse_embedding_response(
            request.model_ref, payload, self._clock() - started,
        )

    def unload(self, model_ref: str) -> None:
        self._transport.request(
            "POST",
            self._settings.endpoint("/api/generate"),
            build_unload_payload(model_ref),
            self._settings.timeout_seconds,
        )
        self._wait_until_unloaded(model_ref)

    def prewarm(self, model_ref: str, keep_alive: str = "10m") -> None:
        """Load weights without supplying prompt content, then prove residency."""
        self._transport.request(
            "POST",
            self._settings.endpoint("/api/generate"),
            build_prewarm_payload(model_ref, keep_alive),
            self._settings.timeout_seconds,
        )
        self._wait_until_loaded(model_ref)

    def prewarm_embedding(
        self, model_ref: str, keep_alive: str = "10m",
    ) -> None:
        """Load an embedding-only model through /api/embed and prove residency."""
        self.embed(EmbeddingRequest(
            model_ref, (_EMBEDDING_RESIDENCY_PROBE,), keep_alive,
        ))
        self._wait_until_loaded(model_ref)

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

    def _wait_until_loaded(self, model_ref: str) -> None:
        deadline = self._clock() + self._settings.unload_timeout_seconds
        while not any(model.model_ref == model_ref for model in self.loaded_models()):
            if self._clock() >= deadline:
                raise OllamaTransportError(
                    f"model did not become resident after prewarm: {model_ref}"
                )
            self._sleep(self._settings.unload_poll_seconds)


def _recover_content_tool_call(
    request: InferenceRequest, response: InferenceResponse,
) -> InferenceResponse:
    """Normalize tool-capable Ollama templates that emit calls as JSON content."""
    if response.tool_calls or not request.tools:
        return response
    try:
        value = json.loads(response.content)
    except (json.JSONDecodeError, TypeError):
        return response
    if not isinstance(value, dict) or set(value) != {"name", "arguments"}:
        return response
    name, arguments = value["name"], value["arguments"]
    tools = {item.name: item for item in request.tools}
    if not isinstance(name, str) or name not in tools:
        raise OllamaProtocolError("model selected a tool that was not offered")
    if not isinstance(arguments, dict):
        raise OllamaProtocolError("content tool call arguments must be an object")
    _validate_tool_arguments(arguments, tools[name].parameters)
    digest = hashlib.sha256(response.content.encode("utf-8")).hexdigest()[:16]
    return replace(
        response, content="",
        tool_calls=(InferenceToolCall(
            f"ollama-content-call-{digest}", name, arguments,
        ),),
    )


def _validate_tool_arguments(arguments, schema) -> None:
    properties = schema.get("properties", {})
    required = schema.get("required", [])
    if not isinstance(properties, dict) or not isinstance(required, list):
        raise OllamaProtocolError("offered tool schema is invalid")
    if not set(required).issubset(arguments) or not set(arguments).issubset(properties):
        raise OllamaProtocolError("content tool call arguments do not match the schema")
    expected_types = {
        "string": str, "integer": int, "number": (int, float),
        "boolean": bool, "array": list, "object": dict,
    }
    for name, value in arguments.items():
        definition = properties[name]
        expected = definition.get("type") if isinstance(definition, dict) else None
        accepted = expected_types.get(expected)
        if accepted is not None and (
            not isinstance(value, accepted)
            or expected in {"integer", "number"} and isinstance(value, bool)
        ):
            raise OllamaProtocolError(
                f"content tool call argument {name} has the wrong type"
            )
