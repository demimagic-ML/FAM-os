"""Run the installed product with deterministic grounded JSON generation."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
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
    parser.add_argument("--observations", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    repository = args.repository.resolve()
    sys.path[:] = [str(args.installed_python.resolve())] + [
        item for item in sys.path
        if item and not Path(item).resolve().is_relative_to(repository)
    ]
    from fam_os.product.service import LocalProductService, ProductServiceSettings

    runtime = _GroundedRuntime(args.observations)
    service = LocalProductService(ProductServiceSettings(
        args.state_root, args.runtime_root, console_port=args.port,
        ready_file=args.ready_file, manage_ollama=False,
        source_model_root=args.model_root,
    ), runtime)
    for event in (signal.SIGINT, signal.SIGTERM):
        signal.signal(event, lambda *_unused: service.stop())
    try:
        service.start()
        service.wait()
    finally:
        service.stop()
        runtime.write()
    return 0


class _GroundedRuntime:
    def __init__(self, observations: Path) -> None:
        self._path = observations
        self._items: list[dict[str, object]] = []

    def chat(self, request):
        prompt = request.messages[-1].content
        sources = _sources(prompt)
        if not sources:
            raise RuntimeError("grounded qualification received no declared source")
        source_id, locator, content = sources[0]
        quote = _identity_paragraph(content) if source_id == "fam-os-product-identity" else content.strip()
        self._items.append({
            "model_ref": request.model_ref,
            "json_output": request.json_output,
            "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            "source_locators": [item[1] for item in sources],
            "contains_forbidden_secret": any(
                "MCP_ONLY_PRIVATE_NONCE" in item[2] for item in sources
            ),
        })
        candidate = json.dumps({
            "answer": quote,
            "claims": [{"text": quote, "source_id": source_id, "quote": quote}],
        }, separators=(",", ":"))
        return type("Response", (), {"content": candidate})()

    def embed(self, request):
        from fam_os.core.ports.embedding import EmbeddingResponse
        vectors = tuple(_vector(value) for value in request.inputs)
        return EmbeddingResponse(request.model_ref, vectors, len(vectors), 0.001)

    def loaded_models(self):
        return ()

    def unload(self, _model_ref):
        return None

    def write(self) -> None:
        self._path.write_text(
            json.dumps(self._items, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def _sources(prompt: str) -> list[tuple[str, str, str]]:
    return [
        (match.group(1), match.group(2), match.group(3).strip())
        for match in re.finditer(
            r"(?:^|\n\n)SOURCE ([^ ]+) \(([^)]+)\)\n(.*?)(?=\n\nSOURCE |\Z)",
            prompt, re.DOTALL,
        )
    ]


def _identity_paragraph(content: str) -> str:
    return next(
        line for line in content.splitlines()
        if line.startswith("FAM_OS is a local, user-controlled")
    )


def _vector(value: str) -> tuple[float, float, float]:
    encoded = value.encode("utf-8")
    return float(len(encoded)), float(sum(encoded) % 997), 1.0


if __name__ == "__main__":
    raise SystemExit(main())
