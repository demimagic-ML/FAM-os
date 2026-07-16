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
        "messages": [
            {"role": message.role.value, "content": message.content}
            for message in request.messages
        ],
        "think": False,
        "options": options,
    }
    if request.json_output:
        payload["format"] = "json"
    return payload


def build_unload_payload(model_ref: str) -> JsonObject:
    if not model_ref.strip():
        raise ValueError("model_ref must not be empty")
    return {"model": model_ref, "keep_alive": 0}


def build_embedding_payload(request: EmbeddingRequest) -> JsonObject:
    return {
        "model": request.model_ref,
        "input": list(request.inputs),
        "keep_alive": request.keep_alive,
    }
