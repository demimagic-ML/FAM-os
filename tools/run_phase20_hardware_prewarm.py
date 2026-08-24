#!/usr/bin/env python3
"""Qualify prompt-free prewarm against downloaded strong Ollama models."""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

from fam_os.adapters.ollama import OllamaRuntime, OllamaSettings


MODELS = ("gemma4:26b", "laguna-xs.2:q4_K_M")


def main() -> int:
    repository = Path(__file__).resolve().parents[1]
    output = repository / "artifacts/adaptation/phase20.6-hardware-prewarm.json"
    runtime = OllamaRuntime(OllamaSettings(
        "http://127.0.0.1:11434", 600, unload_timeout_seconds=60,
    ))
    trials = tuple(_trial(runtime, model_ref) for model_ref in MODELS)
    document = {
        "phase": "20.6", "kind": "physical-ollama-model-prewarm",
        "models": MODELS, "trials": trials,
        "prompt_content_sent": False,
        "sequential_no_eviction_request": True,
    }
    document["passed"] = all(
        item["became_resident"] and item["unloaded_after_trial"]
        for item in trials
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    print(json.dumps(document, indent=2, sort_keys=True))
    return 0 if document["passed"] else 1


def _trial(runtime: OllamaRuntime, model_ref: str) -> dict:
    before = _models(runtime)
    started = time.perf_counter()
    try:
        runtime.prewarm(model_ref, "2m")
        elapsed = time.perf_counter() - started
        after = _models(runtime)
        reading = next(item for item in after if item["model_ref"] == model_ref)
        return {
            "model_ref": model_ref,
            "loaded_before": model_ref in {item["model_ref"] for item in before},
            "became_resident": True,
            "prewarm_seconds": elapsed,
            "resident_bytes": reading["resident_bytes"],
            "accelerator_bytes": reading["accelerator_bytes"],
            "context_tokens": reading["context_tokens"],
            "nvidia_memory_used_mib": _nvidia_memory(),
            "unloaded_after_trial": _unload(runtime, model_ref),
        }
    finally:
        if model_ref in {item["model_ref"] for item in _models(runtime)}:
            runtime.unload(model_ref)


def _unload(runtime: OllamaRuntime, model_ref: str) -> bool:
    runtime.unload(model_ref)
    return model_ref not in {item["model_ref"] for item in _models(runtime)}


def _models(runtime: OllamaRuntime) -> tuple[dict, ...]:
    return tuple({
        "model_ref": item.model_ref,
        "resident_bytes": item.resident_bytes,
        "accelerator_bytes": item.accelerator_bytes,
        "context_tokens": item.context_tokens,
    } for item in runtime.loaded_models())


def _nvidia_memory() -> int:
    completed = subprocess.run(
        (
            "nvidia-smi", "--query-gpu=memory.used",
            "--format=csv,noheader,nounits",
        ),
        check=True, capture_output=True, text=True, timeout=30,
    )
    return max(int(value.strip()) for value in completed.stdout.splitlines())


if __name__ == "__main__":
    raise SystemExit(main())
