"""Production policy facade for explicit local document indexing."""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event, Thread
from typing import Callable
from uuid import uuid4

from fam_os.memory import (
    DocumentIndexGrant,
    DocumentIndexGrantKind,
    DocumentIndexReceipt,
    MemoryScope,
)
from fam_os.memory.document_ingestion import SecureDocumentIngestor
from fam_os.product.storage.document_index_repository import (
    SqliteProductDocumentIndexRepository,
)


SAFE_TEXT_EXTENSIONS = (
    ".css", ".csv", ".html", ".ini", ".js", ".json", ".md", ".py",
    ".rst", ".toml", ".ts", ".tsx", ".txt", ".yaml", ".yml",
)


class ProductDocumentIndexService:
    def __init__(
        self,
        repository: SqliteProductDocumentIndexRepository,
        ingestor: SecureDocumentIngestor,
        owner_id: str,
        embedding_model_ref: str,
        embedding_artifact_sha256: str,
        clock: Callable[[], datetime] | None = None,
        management=None,
    ) -> None:
        self._repository = repository
        self._ingestor = ingestor
        self._owner_id = owner_id
        self._model_ref = embedding_model_ref
        self._artifact_sha256 = embedding_artifact_sha256
        self._clock = clock or (lambda: datetime.now(UTC))
        self.management = management
        self._changed = Event()
        self._stopped = Event()
        self._worker: Thread | None = None

    def start(self) -> None:
        if self._worker is not None:
            return
        self._worker = Thread(target=self._expiry_loop, daemon=True)
        self._worker.start()

    def close(self) -> None:
        self._stopped.set()
        self._changed.set()
        if self._worker is not None:
            self._worker.join(timeout=5)
            self._worker = None

    def create(self, document: dict) -> DocumentIndexReceipt:
        _exact_fields(document, {
            "path", "kind", "recursive", "purpose_ids", "application_ids",
            "workspace_ids", "allowed_extensions", "max_files", "max_file_bytes",
            "max_total_bytes", "expires_in_hours", "expires_in_seconds", "confirmed",
        })
        if document.get("confirmed") is not True:
            raise PermissionError("persistent document indexing requires confirmed=true")
        now = self._clock()
        extensions = _extensions(document.get("allowed_extensions", (".md", ".txt")))
        lifetime = _lifetime(document)
        grant = DocumentIndexGrant(
            grant_id=str(uuid4()),
            root_path=_absolute_path(document.get("path")),
            kind=DocumentIndexGrantKind(document.get("kind")),
            scope=MemoryScope(
                self._owner_id,
                _strings(document.get("purpose_ids", ("assist",)), "purpose_ids", True),
                _strings(document.get("application_ids", ()), "application_ids"),
                _strings(document.get("workspace_ids", ()), "workspace_ids"),
            ),
            recursive=_boolean(document.get("recursive", False), "recursive"),
            allowed_extensions=extensions,
            max_files=_integer(document.get("max_files", 128), "max_files"),
            max_file_bytes=_integer(
                document.get("max_file_bytes", 1_048_576), "max_file_bytes",
            ),
            max_total_bytes=_integer(
                document.get("max_total_bytes", 16_777_216), "max_total_bytes",
            ),
            approved_by=self._owner_id,
            approved_at=now,
            expires_at=now + lifetime,
            embedding_model_ref=self._model_ref,
            embedding_artifact_sha256=self._artifact_sha256,
        )
        receipt = self._ingestor.index(grant, confirmed=True)
        self._changed.set()
        return receipt

    def list(self) -> list[dict]:
        now = self._clock()
        self._repository.purge_expired(now)
        return [_json_value(asdict(grant)) for grant in self._repository.grants()]

    def _expiry_loop(self) -> None:
        while not self._stopped.is_set():
            now = self._clock()
            self._repository.purge_expired(now)
            grants = self._repository.grants()
            delay = 300.0
            if grants:
                delay = max(0.01, min(
                    delay, min((grant.expires_at - now).total_seconds() for grant in grants),
                ))
            self._changed.wait(delay)
            self._changed.clear()


def _exact_fields(document: dict, allowed: set[str]) -> None:
    unknown = set(document) - allowed
    if unknown:
        raise ValueError(f"unknown document index fields: {', '.join(sorted(unknown))}")


def _absolute_path(value: object) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise ValueError("document index path must be a non-empty absolute path")
    path = Path(value)
    if not path.is_absolute():
        raise ValueError("document index path must be absolute")
    return str(path)


def _strings(value: object, name: str, required: bool = False) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{name} must be an array of strings")
    result = tuple(value)
    if required and not result:
        raise ValueError(f"{name} must not be empty")
    return result


def _extensions(value: object) -> tuple[str, ...]:
    extensions = tuple(sorted(set(_strings(value, "allowed_extensions", True))))
    if any(item not in SAFE_TEXT_EXTENSIONS for item in extensions):
        raise ValueError("document index extension is outside the safe text allowlist")
    return extensions


def _integer(value: object, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{name} must be an integer")
    return value


def _lifetime(document: dict) -> timedelta:
    if "expires_in_seconds" in document and "expires_in_hours" in document:
        raise ValueError("choose either expires_in_seconds or expires_in_hours")
    if "expires_in_seconds" in document:
        seconds = _integer(document["expires_in_seconds"], "expires_in_seconds")
    else:
        hours = _integer(document.get("expires_in_hours", 168), "expires_in_hours")
        seconds = hours * 3_600
    if not 1 <= seconds <= 7_776_000:
        raise ValueError("document index expiry must be between 1 second and 90 days")
    return timedelta(seconds=seconds)


def _boolean(value: object, name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be boolean")
    return value


def _json_value(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    return value
