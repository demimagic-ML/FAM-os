"""Pure parsing of Ollama responses into provider-neutral contracts."""

from __future__ import annotations

from fam_os.adapters.ollama.errors import OllamaProtocolError
from fam_os.adapters.ollama.transport import JsonObject
from fam_os.core.ports.inference import (
    InferenceResponse, InferenceToolCall, LoadedModel,
)
from fam_os.core.ports.embedding import EmbeddingResponse
from fam_os.telemetry import InferenceMetrics


def _optional_integer(payload: JsonObject, key: str) -> int | None:
    value = payload.get(key)
    if value is None:
        return None
    if isinstance(value, bool):
        raise OllamaProtocolError(f"{key} must be an integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise OllamaProtocolError(f"{key} must be an integer") from exc
    if parsed < 0:
        raise OllamaProtocolError(f"{key} cannot be negative")
    return parsed


def parse_chat_response(
    model_ref: str,
    payload: JsonObject,
    wall_seconds: float,
) -> InferenceResponse:
    message = payload.get("message")
    if not isinstance(message, dict) or not isinstance(message.get("content"), str):
        raise OllamaProtocolError("chat response requires message.content")
    tool_calls = _tool_calls(message.get("tool_calls", []))
    content = message.get("content", "")
    reasoning = (
        message.get("thinking") if isinstance(message.get("thinking"), str)
        else None
    )
    output_tokens = _optional_integer(payload, "eval_count") or 0
    duration_ns = _optional_integer(payload, "eval_duration") or 0
    rate = output_tokens / (duration_ns / 1e9) if duration_ns else None
    metrics = InferenceMetrics(
        model_ref=model_ref,
        wall_seconds=wall_seconds,
        load_seconds=(_optional_integer(payload, "load_duration") or 0) / 1e9,
        prompt_tokens=_optional_integer(payload, "prompt_eval_count") or 0,
        output_tokens=output_tokens,
        generation_tokens_per_second=rate,
    )
    done_reason = payload.get("done_reason")
    if done_reason is not None and not isinstance(done_reason, str):
        raise OllamaProtocolError("done_reason must be text")
    if not content and not tool_calls and not reasoning and not done_reason:
        raise OllamaProtocolError(
            "chat response requires output or a terminal finish reason"
        )
    return InferenceResponse(
        content=content, metrics=metrics, tool_calls=tool_calls,
        finish_reason=done_reason,
        reasoning_content=reasoning,
    )


def _tool_calls(raw: object) -> tuple[InferenceToolCall, ...]:
    if not isinstance(raw, list):
        raise OllamaProtocolError("message.tool_calls must be a list")
    values = []
    for index, item in enumerate(raw, 1):
        if not isinstance(item, dict) or not isinstance(item.get("function"), dict):
            raise OllamaProtocolError("tool call requires function")
        function = item["function"]
        name, arguments = function.get("name"), function.get("arguments")
        if not isinstance(name, str) or not isinstance(arguments, dict):
            raise OllamaProtocolError("tool call function is invalid")
        call_id = item.get("id", f"ollama-call-{index}")
        if not isinstance(call_id, str):
            raise OllamaProtocolError("tool call id must be text")
        values.append(InferenceToolCall(call_id, name, arguments))
    return tuple(values)


def parse_loaded_models(payload: JsonObject) -> tuple[LoadedModel, ...]:
    raw_models = payload.get("models", [])
    if not isinstance(raw_models, list):
        raise OllamaProtocolError("models response requires a list")
    return tuple(_parse_loaded_model(model) for model in raw_models)


def _parse_loaded_model(raw: object) -> LoadedModel:
    if not isinstance(raw, dict):
        raise OllamaProtocolError("loaded model must be an object")
    model_ref = raw.get("model") or raw.get("name")
    if not isinstance(model_ref, str) or not model_ref.strip():
        raise OllamaProtocolError("loaded model requires model or name")
    return LoadedModel(
        model_ref=model_ref,
        resident_bytes=_optional_integer(raw, "size"),
        accelerator_bytes=_optional_integer(raw, "size_vram"),
        context_tokens=_optional_integer(raw, "context_length"),
    )


def parse_embedding_response(
    model_ref: str, payload: JsonObject, wall_seconds: float,
) -> EmbeddingResponse:
    raw_vectors = payload.get("embeddings")
    if not isinstance(raw_vectors, list) or not raw_vectors:
        raise OllamaProtocolError("embedding response requires embeddings")
    vectors = tuple(_parse_vector(value) for value in raw_vectors)
    return EmbeddingResponse(
        model_ref=model_ref,
        vectors=vectors,
        prompt_tokens=_optional_integer(payload, "prompt_eval_count") or 0,
        wall_seconds=wall_seconds,
    )


def _parse_vector(raw: object) -> tuple[float, ...]:
    if not isinstance(raw, list) or not raw:
        raise OllamaProtocolError("embedding vector must be a non-empty list")
    try:
        vector = tuple(float(value) for value in raw)
    except (TypeError, ValueError) as exc:
        raise OllamaProtocolError("embedding vector values must be numeric") from exc
    return vector
