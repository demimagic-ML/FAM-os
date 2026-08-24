"""Pure translation from FAM contracts to Ollama request JSON."""

from __future__ import annotations

from fam_os.adapters.ollama.transport import JsonObject
from fam_os.core.ports.inference import InferenceRequest
from fam_os.core.ports.embedding import EmbeddingRequest


def build_chat_payload(request: InferenceRequest) -> JsonObject:
    options: JsonObject = {
        "num_ctx": request.context_tokens,
        "temperature": request.temperature,
        "num_predict": request.max_output_tokens,
    }
    if request.seed is not None:
        options["seed"] = request.seed
    if request.accelerator_layer_count is not None:
        options["num_gpu"] = request.accelerator_layer_count
    if request.main_accelerator_index is not None:
        options["main_gpu"] = request.main_accelerator_index
    payload: JsonObject = {
        "model": request.model_ref,
        "stream": False,
        "keep_alive": request.keep_alive,
        "messages": [_message_payload(message) for message in request.messages],
        "think": False,
        "options": options,
    }
    if request.tools:
        payload["tools"] = [
            {
                "type": "function",
                "function": {
                    "name": item.name,
                    "description": item.description,
                    "parameters": item.parameters,
                },
            }
            for item in request.tools
        ]
        if request.tool_choice is not None:
            payload["tool_choice"] = request.tool_choice
    elif request.json_output:
        payload["format"] = "json"
    return payload


def _message_payload(message) -> JsonObject:
    import base64

    value: JsonObject = {"role": message.role.value, "content": message.content}
    if message.images:
        value["images"] = [base64.b64encode(item).decode("ascii") for item in message.images]
    if message.tool_calls:
        value["tool_calls"] = [
            {
                "function": {
                    "name": item.name,
                    "arguments": item.arguments,
                },
            }
            for item in message.tool_calls
        ]
    if message.tool_name is not None:
        value["tool_name"] = message.tool_name
    return value


def build_unload_payload(model_ref: str) -> JsonObject:
    if not model_ref.strip():
        raise ValueError("model_ref must not be empty")
    return {"model": model_ref, "keep_alive": 0}


def build_prewarm_payload(model_ref: str, keep_alive: str) -> JsonObject:
    if not model_ref.strip() or not keep_alive.strip():
        raise ValueError("prewarm model and keep_alive must not be empty")
    return {"model": model_ref, "stream": False, "keep_alive": keep_alive}


def build_embedding_payload(request: EmbeddingRequest) -> JsonObject:
    return {
        "model": request.model_ref,
        "input": list(request.inputs),
        "keep_alive": request.keep_alive,
    }
