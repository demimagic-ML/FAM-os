"""Pure parsing of Ollama responses into provider-neutral contracts."""

from __future__ import annotations

from fam_os.adapters.ollama.errors import OllamaProtocolError
from fam_os.adapters.ollama.transport import JsonObject
from fam_os.core.ports.inference import InferenceResponse, LoadedModel
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
    return InferenceResponse(content=message["content"], metrics=metrics)


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

