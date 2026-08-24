"""Run the installed product with a deterministic residency-aware runtime."""

from __future__ import annotations

import argparse
import json
import signal
import sys
from pathlib import Path
from threading import Lock


PRIMARY = "qwen2.5-coder:7b"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--installed-python", type=Path, required=True)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--ready-file", type=Path, required=True)
    parser.add_argument("--responses", type=Path, required=True)
    parser.add_argument("--telemetry", type=Path, required=True)
    parser.add_argument("--health", type=Path)
    parser.add_argument("--source-model-root", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    _installed_imports(args.installed_python, args.repository)
    from fam_os.product.service import LocalProductService, ProductServiceSettings

    runtime = _Runtime(args.responses, args.telemetry)
    health_sampler = None if args.health is None else _HealthSampler(args.health)
    service = LocalProductService(
        ProductServiceSettings(
            args.state_root,
            args.runtime_root,
            console_port=args.port,
            ready_file=args.ready_file,
            manage_ollama=False,
            source_model_root=args.source_model_root,
        ),
        runtime,
        adaptation_health_sampler=health_sampler,
    )
    for event in (signal.SIGINT, signal.SIGTERM):
        signal.signal(event, lambda *_unused: service.stop())
    try:
        service.start()
        service.wait()
    finally:
        service.stop()
    return 0


class _Runtime:
    def __init__(self, responses: Path, telemetry: Path) -> None:
        self._responses = list(json.loads(responses.read_text(encoding="utf-8")))
        self._telemetry = telemetry
        self._lock = Lock()
        self._chat_count = 0
        self._prewarmed: set[str] = set()

    def chat(self, request):
        with self._lock:
            if not self._responses:
                raise RuntimeError("Phase 20.6 restart attempted unexpected inference")
            scripted = self._responses.pop(0)
            if scripted["model_ref"] != request.model_ref:
                raise RuntimeError(
                    f"expected {scripted['model_ref']}, received {request.model_ref}"
                )
            self._chat_count += 1
            self._write(
                {
                    "kind": "chat",
                    "sequence": self._chat_count,
                    "model_ref": request.model_ref,
                    "context_tokens": request.context_tokens,
                    "content": scripted["content"],
                    "wall_seconds": scripted.get("wall_seconds", 0.1),
                }
            )
            from fam_os.core.ports import InferenceResponse
            from fam_os.telemetry import InferenceMetrics

            return InferenceResponse(
                scripted["content"],
                InferenceMetrics(
                    request.model_ref,
                    scripted.get("wall_seconds", 0.1),
                    scripted.get("load_seconds", 0.0),
                    scripted.get("prompt_tokens", 64),
                    scripted.get("output_tokens", 8),
                    scripted.get("generation_tokens_per_second", 80.0),
                ),
            )

    def loaded_models(self):
        with self._lock:
            refs = tuple(sorted(self._prewarmed))
            if not refs and self._chat_count:
                refs = (PRIMARY,)
            return tuple(type("Loaded", (), {"model_ref": value})() for value in refs)

    def prewarm(self, model_ref, keep_alive="10m"):
        with self._lock:
            self._prewarmed.add(model_ref)
            self._write(
                {
                    "kind": "prewarm",
                    "model_ref": model_ref,
                    "keep_alive": keep_alive,
                    "prompt_supplied": False,
                }
            )

    def unload(self, model_ref):
        with self._lock:
            self._prewarmed.discard(model_ref)

    def embed(self, request):
        vectors = tuple((float(len(value)), 1.0) for value in request.inputs)
        return type(
            "Embedding",
            (),
            {
                "model_ref": request.model_ref,
                "vectors": vectors,
                "prompt_tokens": len(request.inputs),
                "wall_seconds": 0.001,
            },
        )()

    def _write(self, event: dict) -> None:
        with self._telemetry.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, sort_keys=True) + "\n")
            stream.flush()


class _HealthSampler:
    def __init__(self, path: Path) -> None:
        self._values = list(json.loads(path.read_text(encoding="utf-8")))
        self._lock = Lock()

    def __call__(self):
        from fam_os.adaptation import AdaptationRuntimeHealth

        with self._lock:
            if not self._values:
                raise RuntimeError("Phase 20.7 health sample script was exhausted")
            value = self._values.pop(0)
        return AdaptationRuntimeHealth(
            value.get("peak_temperature_c"),
            value["policy_conformant"],
            tuple(value["reason_codes"]),
        )


def _installed_imports(installed_python: Path, repository: Path) -> None:
    root = repository.resolve()
    sys.path[:] = [str(installed_python.resolve())] + [
        item
        for item in sys.path
        if item and not Path(item).resolve().is_relative_to(root)
    ]


if __name__ == "__main__":
    raise SystemExit(main())
