"""Minimal valid local Ollama store for installed index qualification."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def create_model_root(root: Path) -> Path:
    payload = b"phase20-index-model"
    digest = hashlib.sha256(payload).hexdigest()
    blob = root / "blobs" / f"sha256-{digest}"
    blob.parent.mkdir(parents=True)
    blob.write_bytes(payload)
    manifest = json.dumps({
        "config": {"digest": f"sha256:{digest}"}, "layers": [],
    }, sort_keys=True)
    for name, tag in (("qwen3", "1.7b"), ("nomic-embed-text", "latest")):
        path = root / "manifests/registry.ollama.ai/library" / name / tag
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(manifest, encoding="utf-8")
    return root
