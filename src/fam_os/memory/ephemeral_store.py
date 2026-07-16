"""Bounded digest-verifying session and working memory store."""

import hashlib
from dataclasses import dataclass
from datetime import datetime

from fam_os.memory.access import MemoryAccessContext, scope_allows
from fam_os.memory.lifecycle_contracts import MemoryDeletionReceipt, MemoryDeletionRequest
from fam_os.memory.manifest import MemoryRecordKind, MemoryRecordManifest


@dataclass(frozen=True, slots=True)
class StoredMemoryRecord:
    manifest: MemoryRecordManifest
    content: bytes


class BoundedEphemeralMemoryStore:
    def __init__(self, maximum_records: int, maximum_bytes: int) -> None:
        if maximum_records <= 0 or maximum_bytes <= 0:
            raise ValueError("memory store bounds must be positive")
        self._maximum_records = maximum_records
        self._maximum_bytes = maximum_bytes
        self._records: dict[str, StoredMemoryRecord] = {}
        self._bytes = 0

    def put(self, manifest: MemoryRecordManifest, content: bytes) -> None:
        if manifest.kind not in (MemoryRecordKind.SESSION, MemoryRecordKind.WORKING):
            raise ValueError("ephemeral store accepts session and working memory only")
        _verify_content(manifest, content)
        if manifest.record_id in self._records:
            raise ValueError("memory record ID already exists")
        if len(self._records) >= self._maximum_records or self._bytes + len(content) > self._maximum_bytes:
            raise MemoryError("ephemeral memory capacity exceeded")
        self._records[manifest.record_id] = StoredMemoryRecord(manifest, bytes(content))
        self._bytes += len(content)

    def get(self, record_id: str, context: MemoryAccessContext, now: datetime) -> StoredMemoryRecord | None:
        record = self._records.get(record_id)
        if record is None or _expired(record.manifest, now):
            return None
        return record if scope_allows(record.manifest.scope, context) else None

    def inspect(self, context: MemoryAccessContext, now: datetime) -> tuple[MemoryRecordManifest, ...]:
        return tuple(
            item.manifest for item in self._records.values()
            if not _expired(item.manifest, now) and scope_allows(item.manifest.scope, context)
        )

    def delete(self, request: MemoryDeletionRequest, now: datetime) -> MemoryDeletionReceipt:
        record = self._records.get(request.record_id)
        if record is None or record.manifest.scope.owner_id != request.owner_id:
            raise PermissionError("memory deletion owner does not match record")
        del self._records[request.record_id]
        self._bytes -= len(record.content)
        tombstone = f"{request.request_id}|{request.record_id}|{now.isoformat()}"
        return MemoryDeletionReceipt(
            request.request_id, request.record_id, now,
            record.manifest.content_digest.value,
            hashlib.sha256(tombstone.encode()).hexdigest(), True,
        )

    def purge_expired(self, now: datetime) -> tuple[str, ...]:
        expired = tuple(key for key, value in self._records.items() if _expired(value.manifest, now))
        for key in expired:
            self._bytes -= len(self._records.pop(key).content)
        return expired


def _verify_content(manifest: MemoryRecordManifest, content: bytes) -> None:
    if manifest.content_digest.algorithm != "sha256":
        raise ValueError("ephemeral memory requires SHA-256 content digests")
    if len(content) != manifest.content_size_bytes:
        raise ValueError("memory content size does not match manifest")
    if hashlib.sha256(content).hexdigest() != manifest.content_digest.value:
        raise ValueError("memory content digest does not match manifest")


def _expired(manifest: MemoryRecordManifest, now: datetime) -> bool:
    if now.tzinfo is None:
        raise ValueError("memory access time must be timezone-aware")
    return manifest.expires_at is not None and now >= manifest.expires_at
