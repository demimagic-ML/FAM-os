"""Explicit, bounded, symlink-safe local document ingestion."""

from __future__ import annotations

import hashlib
import os
import stat
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, Protocol
from uuid import uuid4

from fam_os.memory.document_contracts import DocumentIndexApproval
from fam_os.memory.document_index import ApprovedDocumentIndex
from fam_os.memory.grant_contracts import (
    DocumentIndexGrant,
    DocumentIndexGrantKind,
    DocumentIndexReceipt,
)


class DocumentGrantRepository(Protocol):
    def add_grant(self, grant: DocumentIndexGrant) -> bool: ...
    def delete_grant(self, grant_id: str) -> bool: ...
    def purge_expired(self, now: datetime) -> tuple[str, ...]: ...


class IndexModelLoader(Protocol):
    def ensure_model(self, model_ref: str) -> None: ...


@dataclass(frozen=True, slots=True)
class _Source:
    path: Path
    relative_path: str
    content: str
    size_bytes: int


class SecureDocumentIngestor:
    def __init__(
        self,
        repository: DocumentGrantRepository,
        index: ApprovedDocumentIndex,
        owner_uid: int,
        model_loader: IndexModelLoader | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if owner_uid < 0:
            raise ValueError("document ingestor owner UID is invalid")
        self._repository = repository
        self._index = index
        self._owner_uid = owner_uid
        self._model_loader = model_loader
        self._clock = clock or (lambda: datetime.now(UTC))

    def index(self, grant: DocumentIndexGrant, *, confirmed: bool) -> DocumentIndexReceipt:
        if not confirmed:
            raise PermissionError("persistent document indexing requires explicit confirmation")
        now = self._clock()
        if not grant.active_at(now):
            raise PermissionError("document index grant is not active")
        self._repository.purge_expired(now)
        if self._model_loader is not None:
            self._model_loader.ensure_model(grant.embedding_model_ref)
        sources, skipped = self._read_sources(grant)
        if not sources:
            raise ValueError("document index grant contains no eligible UTF-8 documents")
        if not self._repository.add_grant(grant):
            raise ValueError("document index grant identity already exists")
        identifiers: list[str] = []
        chunk_count = 0
        indexed_bytes = 0
        try:
            for source in sources:
                document_id = _document_id(grant.grant_id, source.relative_path)
                chunks = document_chunks(source.content)
                if not chunks:
                    skipped.append(source.relative_path)
                    continue
                approval = DocumentIndexApproval(
                    document_id=document_id,
                    source_locator=source.path.as_uri(),
                    source_sha256=hashlib.sha256(source.content.encode("utf-8")).hexdigest(),
                    scope=grant.scope,
                    approved_by=grant.approved_by,
                    approved_at=now,
                    embedding_model_ref=grant.embedding_model_ref,
                    embedding_artifact_sha256=grant.embedding_artifact_sha256,
                    grant_id=grant.grant_id,
                    expires_at=grant.expires_at,
                )
                self._index.index(approval, source.content, chunks)
                identifiers.append(document_id)
                chunk_count += len(chunks)
                indexed_bytes += source.size_bytes
            if not identifiers:
                raise ValueError("document index grant contains no nonblank documents")
        except BaseException:
            self._repository.delete_grant(grant.grant_id)
            raise
        return DocumentIndexReceipt(
            str(uuid4()), grant.grant_id, tuple(identifiers), chunk_count,
            indexed_bytes, tuple(sorted(skipped)),
            now, grant.expires_at, True,
        )

    def _read_sources(self, grant: DocumentIndexGrant) -> tuple[list[_Source], list[str]]:
        root = Path(grant.root_path)
        if grant.kind is DocumentIndexGrantKind.FILE:
            return [_read_file_path(root, grant, self._owner_uid)], []
        descriptor = _open_directory_path(root)
        try:
            metadata = os.fstat(descriptor)
            if metadata.st_uid != self._owner_uid:
                raise PermissionError("document index root must be owned by the service user")
            state = _ScanState([], [], 0, 0)
            _scan_directory(descriptor, root, Path(), grant, self._owner_uid, state)
            return state.sources, state.skipped
        finally:
            os.close(descriptor)


@dataclass(slots=True)
class _ScanState:
    sources: list[_Source]
    skipped: list[str]
    scanned: int
    total_bytes: int


def _scan_directory(
    descriptor: int, root: Path, relative: Path, grant: DocumentIndexGrant,
    owner_uid: int, state: _ScanState,
) -> None:
    for name in sorted(os.listdir(descriptor)):
        state.scanned += 1
        if state.scanned > max(256, grant.max_files * 16):
            raise ValueError("document folder traversal exceeds its derived scan bound")
        metadata = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
        child_relative = relative / name
        display = child_relative.as_posix()
        if stat.S_ISLNK(metadata.st_mode):
            state.skipped.append(display)
        elif stat.S_ISDIR(metadata.st_mode) and grant.recursive:
            child = _open_directory_entry(descriptor, name)
            try:
                _scan_directory(child, root, child_relative, grant, owner_uid, state)
            finally:
                os.close(child)
        elif stat.S_ISREG(metadata.st_mode) and Path(name).suffix.lower() in grant.allowed_extensions:
            if len(state.sources) >= grant.max_files:
                raise ValueError("eligible document count exceeds the approved file bound")
            try:
                source = _read_file_entry(
                    descriptor, name, root / child_relative, display,
                    owner_uid, grant.max_file_bytes,
                )
            except (OSError, UnicodeError, PermissionError, ValueError):
                state.skipped.append(display)
                continue
            state.total_bytes += source.size_bytes
            if state.total_bytes > grant.max_total_bytes:
                raise ValueError("document index content exceeds the approved total byte bound")
            state.sources.append(source)


def _read_file_path(path: Path, grant: DocumentIndexGrant, owner_uid: int) -> _Source:
    if path.suffix.lower() not in grant.allowed_extensions:
        raise ValueError("document file extension is outside the approved allowlist")
    parent = _open_directory_path(path.parent)
    try:
        return _read_file_entry(
            parent, path.name, path, path.name, owner_uid, grant.max_file_bytes,
        )
    finally:
        os.close(parent)


def _open_directory_path(path: Path) -> int:
    descriptor = os.open(path.anchor, _directory_flags())
    try:
        for part in path.parts[1:]:
            child = _open_directory_entry(descriptor, part)
            os.close(descriptor)
            descriptor = child
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _open_directory_entry(parent: int, name: str) -> int:
    metadata = os.stat(name, dir_fd=parent, follow_symlinks=False)
    if stat.S_ISLNK(metadata.st_mode):
        raise OSError("document index path cannot contain symlinks")
    return os.open(name, _directory_flags(), dir_fd=parent)


def _directory_flags() -> int:
    return (
        os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    )


def _read_file_entry(
    parent: int, name: str, path: Path, relative_path: str,
    owner_uid: int, maximum: int,
) -> _Source:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    descriptor = os.open(name, flags, dir_fd=parent)
    try:
        content, size = _read_descriptor(descriptor, owner_uid, maximum)
        return _Source(path, relative_path, content, size)
    finally:
        os.close(descriptor)


def _read_descriptor(descriptor: int, owner_uid: int, maximum: int) -> tuple[str, int]:
    before = os.fstat(descriptor)
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
        raise OSError("document index source must be one regular non-hardlinked file")
    if before.st_uid != owner_uid:
        raise PermissionError("document index source must be owned by the service user")
    if before.st_size > maximum:
        raise ValueError("document index source exceeds the approved per-file byte bound")
    data = bytearray()
    while len(data) <= maximum:
        chunk = os.read(descriptor, min(65_536, maximum + 1 - len(data)))
        if not chunk:
            break
        data.extend(chunk)
    after = os.fstat(descriptor)
    if len(data) > maximum or _stat_identity(before) != _stat_identity(after):
        raise OSError("document index source changed or exceeded its bound while reading")
    return data.decode("utf-8", errors="strict"), len(data)


def _stat_identity(value: os.stat_result) -> tuple[int, int, int, int, int]:
    return value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns


def _document_id(grant_id: str, relative_path: str) -> str:
    digest = hashlib.sha256(f"{grant_id}\x00{relative_path}".encode()).hexdigest()
    return f"document-{digest}"


def document_chunks(content: str, maximum_bytes: int = 8_192) -> tuple[str, ...]:
    if not content.strip():
        return ()
    raw = content.encode("utf-8")
    chunks: list[str] = []
    offset = 0
    while offset < len(raw):
        end = min(offset + maximum_bytes, len(raw))
        while end > offset:
            try:
                value = raw[offset:end].decode("utf-8")
                break
            except UnicodeDecodeError:
                end -= 1
        else:
            raise UnicodeError("document chunk cannot be decoded as UTF-8")
        if not value.strip() and chunks:
            merged = chunks[-1] + value
            if len(merged.encode("utf-8")) > maximum_bytes * 2:
                raise ValueError("document contains an excessive whitespace run")
            chunks[-1] = merged
        else:
            chunks.append(value)
        offset = end
    if chunks and not chunks[0].strip():
        if len(chunks) == 1:
            return ()
        chunks[1] = chunks[0] + chunks[1]
        chunks.pop(0)
    if any(not value.strip() for value in chunks) or "".join(chunks) != content:
        raise ValueError("document chunking failed to preserve nonblank source content")
    return tuple(chunks)
