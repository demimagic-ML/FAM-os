"""Privacy-bounded Ollama model blob and mmap page-cache observation."""

from __future__ import annotations

import ctypes
import json
import mmap
import os
import stat
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from fam_os.scheduler.storage_contracts import ArtifactCacheObservation


MODEL_MEDIA_TYPE = "application/vnd.ollama.image.model"


@dataclass(frozen=True, slots=True)
class ResolvedModelBlob:
    artifact_id: str
    model_ref: str
    digest_sha256: str
    declared_bytes: int
    path: Path


@dataclass(frozen=True, slots=True)
class OllamaModelBlobResolver:
    model_root: Path

    def resolve(self, model_ref: str) -> ResolvedModelBlob:
        name, tag = _model_coordinate(model_ref)
        manifest = self.model_root / "manifests/registry.ollama.ai/library" / name / tag
        _require_beneath(manifest, self.model_root)
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        layer = next(item for item in payload["layers"] if item["mediaType"] == MODEL_MEDIA_TYPE)
        digest = layer["digest"].removeprefix("sha256:")
        path = self.model_root / "blobs" / f"sha256-{digest}"
        _require_regular(path, self.model_root)
        size = path.stat().st_size
        if size != layer["size"]:
            raise ValueError("Ollama model blob size differs from manifest")
        return ResolvedModelBlob(
            f"ollama-blob:{digest}", model_ref, digest, layer["size"], path
        )


@dataclass(frozen=True, slots=True)
class MmapPageCacheObserver:
    allowed_root: Path

    def observe(self, blob: ResolvedModelBlob, observation_id: str) -> ArtifactCacheObservation:
        _require_regular(blob.path, self.allowed_root)
        page_size = mmap.PAGESIZE
        pages = (blob.declared_bytes + page_size - 1) // page_size
        resident = _resident_pages(blob.path, pages)
        return ArtifactCacheObservation(
            observation_id, blob.artifact_id, datetime.now(timezone.utc),
            blob.declared_bytes, page_size, pages, resident,
            min(blob.declared_bytes, resident * page_size), resident / pages, True,
        )

    def evict(self, blob: ResolvedModelBlob) -> None:
        _require_regular(blob.path, self.allowed_root)
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(blob.path, flags)
        try:
            os.posix_fadvise(descriptor, 0, 0, os.POSIX_FADV_DONTNEED)
        finally:
            os.close(descriptor)


def _resident_pages(path: Path, pages: int) -> int:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        mapping = mmap.mmap(descriptor, 0, access=mmap.ACCESS_COPY)
    finally:
        os.close(descriptor)
    try:
        byte = ctypes.c_char.from_buffer(mapping)
        address = ctypes.addressof(byte)
        vector = (ctypes.c_ubyte * pages)()
        library = ctypes.CDLL(None, use_errno=True)
        library.mincore.argtypes = (
            ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_ubyte)
        )
        library.mincore.restype = ctypes.c_int
        try:
            result = library.mincore(address, len(mapping), vector)
            if result != 0:
                error = ctypes.get_errno()
                raise OSError(error, os.strerror(error))
            return sum(value & 1 for value in vector)
        finally:
            del byte
    finally:
        mapping.close()


def _model_coordinate(model_ref: str) -> tuple[str, str]:
    if model_ref.count(":") > 1 or "/" in model_ref or ".." in model_ref:
        raise ValueError("only local Ollama library model references are supported")
    name, separator, tag = model_ref.partition(":")
    return name, tag if separator else "latest"


def _require_regular(path: Path, root: Path) -> None:
    _require_beneath(path, root)
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise ValueError("model blob must be a non-symlink regular file")


def _require_beneath(path: Path, root: Path) -> None:
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("model artifact escaped configured root")
