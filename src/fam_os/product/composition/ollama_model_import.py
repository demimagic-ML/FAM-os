"""Digest-validated hard-link import into the managed Ollama model store."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ImportedOllamaModel:
    model_ref: str
    manifest_path: str
    blob_count: int
    linked_bytes: int


class OllamaModelStoreImporter:
    def __init__(self, source_root: Path, target_root: Path) -> None:
        self._source = source_root
        self._target = target_root

    def import_model(self, model_ref: str) -> ImportedOllamaModel:
        self._target.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self._target, 0o700)
        name, tag = _model_identity(model_ref)
        relative_manifest = Path("manifests/registry.ollama.ai/library") / name / tag
        source_manifest = self._safe_source(relative_manifest)
        manifest = json.loads(source_manifest.read_text(encoding="utf-8"))
        digests = _manifest_digests(manifest)
        linked_bytes = 0
        for digest in digests:
            relative_blob = Path("blobs") / digest.replace(":", "-")
            source_blob = self._safe_source(relative_blob)
            if _sha256(source_blob) != digest.removeprefix("sha256:"):
                raise ValueError(f"Ollama blob digest mismatch: {digest}")
            linked_bytes += source_blob.stat().st_size
            self._link(source_blob, relative_blob)
        self._link(source_manifest, relative_manifest)
        return ImportedOllamaModel(
            model_ref, str(relative_manifest), len(digests), linked_bytes,
        )

    def _safe_source(self, relative: Path) -> Path:
        path = self._source / relative
        if path.is_symlink() or not path.is_file():
            raise FileNotFoundError(f"unsafe or missing Ollama artifact: {relative}")
        if not path.resolve().is_relative_to(self._source.resolve()):
            raise OSError("Ollama artifact escapes source model root")
        return path

    def _link(self, source: Path, relative: Path) -> None:
        target = self._target / relative
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(target.parent, 0o700)
        if target.exists():
            if target.is_symlink() or _sha256(target) != _sha256(source):
                raise FileExistsError(f"managed Ollama artifact conflicts: {relative}")
            return
        try:
            os.link(source, target, follow_symlinks=False)
        except OSError:
            _copy_private(source, target)
        if _sha256(target) != _sha256(source):
            target.unlink(missing_ok=True)
            raise OSError("linked Ollama artifact failed digest verification")


def _model_identity(model_ref: str) -> tuple[str, str]:
    if not model_ref.strip() or "/" in model_ref or "\x00" in model_ref:
        raise ValueError("only local Ollama library model references are supported")
    name, separator, tag = model_ref.partition(":")
    if not name or (separator and not tag):
        raise ValueError("Ollama model reference is invalid")
    return name, tag or "latest"


def _manifest_digests(manifest: object) -> tuple[str, ...]:
    if not isinstance(manifest, dict):
        raise ValueError("Ollama manifest must be an object")
    entries = (manifest.get("config"), *manifest.get("layers", ()))
    digests = []
    for entry in entries:
        digest = entry.get("digest") if isinstance(entry, dict) else None
        if not isinstance(digest, str) or not digest.startswith("sha256:"):
            raise ValueError("Ollama manifest contains an invalid digest")
        digests.append(digest)
    if not digests or len(set(digests)) != len(digests):
        raise ValueError("Ollama manifest digests must be present and unique")
    return tuple(digests)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _copy_private(source: Path, target: Path) -> None:
    descriptor = os.open(
        target,
        os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        with source.open("rb") as input_stream, os.fdopen(descriptor, "wb") as output_stream:
            descriptor = -1
            shutil.copyfileobj(input_stream, output_stream, length=1024 * 1024)
            output_stream.flush()
            os.fsync(output_stream.fileno())
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    finally:
        if descriptor >= 0:
            os.close(descriptor)
