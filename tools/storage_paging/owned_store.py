"""Create a temporary byte-verified Ollama store for cache-control evidence."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path


def clone_model_store(source_root: Path, destination_root: Path, model_ref: str) -> Path:
    name, _, tag = model_ref.partition(":")
    tag = tag or "latest"
    relative_manifest = Path("manifests/registry.ollama.ai/library") / name / tag
    source_manifest = source_root / relative_manifest
    payload = json.loads(source_manifest.read_text(encoding="utf-8"))
    destination_manifest = destination_root / relative_manifest
    destination_manifest.parent.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(source_manifest, destination_manifest)
    _fsync(destination_manifest)
    blobs = (payload["config"], *payload["layers"])
    (destination_root / "blobs").mkdir()
    for item in blobs:
        digest = item["digest"].removeprefix("sha256:")
        source = source_root / "blobs" / f"sha256-{digest}"
        destination = destination_root / "blobs" / f"sha256-{digest}"
        shutil.copyfile(source, destination)
        _fsync(destination)
        if destination.stat().st_size != item["size"]:
            raise ValueError("cloned Ollama blob size differs from manifest")
        if _sha256(destination) != digest:
            raise ValueError("cloned Ollama blob digest differs from manifest")
    return destination_root


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb", buffering=0) as source:
        while chunk := source.read(8 * 1024**2):
            digest.update(chunk)
    return digest.hexdigest()


def _fsync(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
