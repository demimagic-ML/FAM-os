"""Run the installed product with deterministic local embeddings."""

from __future__ import annotations

import argparse
import signal
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--installed-python", type=Path, required=True)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--model-root", type=Path, required=True)
    parser.add_argument("--ready-file", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    repository = args.repository.resolve()
    sys.path[:] = [str(args.installed_python.resolve())] + [
        item for item in sys.path
        if item and not Path(item).resolve().is_relative_to(repository)
    ]
    from fam_os.product.service import LocalProductService, ProductServiceSettings

    service = LocalProductService(ProductServiceSettings(
        args.state_root, args.runtime_root, console_port=args.port,
        ready_file=args.ready_file, manage_ollama=False,
        source_model_root=args.model_root,
    ), _Runtime())
    for event in (signal.SIGINT, signal.SIGTERM):
        signal.signal(event, lambda *_unused: service.stop())
    try:
        service.start()
        service.wait()
    finally:
        service.stop()
    return 0


class _Runtime:
    def chat(self, _request):
        return type("Response", (), {"content": "unused"})()

    def embed(self, request):
        from fam_os.core.ports.embedding import EmbeddingResponse
        vectors = tuple(_vector(value) for value in request.inputs)
        return EmbeddingResponse(request.model_ref, vectors, len(vectors), 0.001)

    def loaded_models(self):
        return ()

    def unload(self, _model_ref):
        return None


def _vector(value: str) -> tuple[float, float, float]:
    encoded = value.encode("utf-8")
    return float(len(encoded)), float(sum(encoded) % 997), 1.0


if __name__ == "__main__":
    raise SystemExit(main())
