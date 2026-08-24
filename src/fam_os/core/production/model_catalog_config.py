"""Strict runtime-model configuration and local artifact observation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from fam_os.core.production.contracts import ModelIntent, RuntimeModelEntry


def catalog_document(serialized: str) -> dict[str, Any]:
    return _strict_json_object(serialized, "runtime model catalog")


def catalog_entries(
    document: dict[str, Any],
    source_root: Path,
    allowed_refs: set[str] | None = None,
) -> tuple[RuntimeModelEntry, ...]:
    if document.get("contract_version") != "fam.product.model-catalog/v1alpha1":
        raise ValueError("runtime model catalog version is unsupported")
    entries = []
    for configured in document.get("models", ()):
        if allowed_refs is not None and configured["model_ref"] not in allowed_refs:
            continue
        manifest = _manifest(source_root, configured["model_ref"])
        if not manifest.is_file() or manifest.is_symlink():
            continue
        digest = hashlib.sha256(manifest.read_bytes()).hexdigest()
        entries.append(RuntimeModelEntry(
            configured["model_ref"], configured["tier"],
            tuple(ModelIntent(value) for value in configured["intents"]),
            _resident_bytes(source_root, manifest),
            int(configured["max_context_tokens"]), digest,
            tuple(configured.get("verifier_ids", ())),
        ))
    return tuple(entries)


def _strict_json_object(serialized: str, subject: str) -> dict[str, Any]:
    try:
        value = json.loads(
            serialized,
            parse_constant=_reject_json_constant,
            object_pairs_hook=_strict_object,
        )
    except (TypeError, json.JSONDecodeError, ValueError) as error:
        raise ValueError(f"{subject} must be strict JSON") from error
    if not isinstance(value, dict):
        raise ValueError(f"{subject} root must be an object")
    return value


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON object key: {key}")
        value[key] = item
    return value


def _reject_json_constant(value: str) -> object:
    raise ValueError(f"non-finite JSON constant: {value}")


def _manifest(root: Path, model_ref: str) -> Path:
    if not model_ref.strip() or "/" in model_ref or "\x00" in model_ref:
        raise ValueError("runtime model reference is unsafe")
    name, separator, tag = model_ref.partition(":")
    if not name or (separator and not tag):
        raise ValueError("runtime model reference is invalid")
    return root / "manifests/registry.ollama.ai/library" / name / (tag or "latest")


def _resident_bytes(root: Path, manifest_path: Path) -> int:
    document = _strict_json_object(
        manifest_path.read_text(encoding="utf-8"), "runtime model manifest",
    )
    entries = (document.get("config"), *document.get("layers", ()))
    total = 0
    for entry in entries:
        digest = entry.get("digest") if isinstance(entry, dict) else None
        if not isinstance(digest, str) or not digest.startswith("sha256:"):
            raise ValueError("runtime model manifest has an invalid digest")
        blob = root / "blobs" / digest.replace(":", "-")
        if blob.is_symlink() or not blob.is_file():
            raise FileNotFoundError(f"runtime model blob is absent: {digest}")
        total += blob.stat().st_size
    if total <= 0:
        raise ValueError("runtime model has no resident artifacts")
    return total
