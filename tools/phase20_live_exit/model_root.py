"""Minimal local model metadata used by the deterministic installed runtime."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


MODELS = (
    "qwen2.5-coder:7b",
    "gemma4:26b",
    "nomic-embed-text:latest",
)


def build_model_root(root: Path) -> Path:
    blobs = root / "blobs"
    blobs.mkdir(parents=True)
    for index, model_ref in enumerate(MODELS):
        content = f"phase20.6-model-{index}-{model_ref}".encode()
        digest = hashlib.sha256(content).hexdigest()
        (blobs / f"sha256-{digest}").write_bytes(content)
        _manifest(root, model_ref).write_text(
            json.dumps({
                "config": {"digest": f"sha256:{digest}"},
                "layers": [],
            }),
            encoding="utf-8",
        )
    return root


def _manifest(root: Path, model_ref: str) -> Path:
    name, tag = model_ref.split(":", 1)
    path = root / "manifests/registry.ollama.ai/library" / name / tag
    path.parent.mkdir(parents=True, exist_ok=True)
    return path
