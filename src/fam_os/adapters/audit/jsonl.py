"""Locked, durable, append-only JSONL SHA-256 audit chain."""

from __future__ import annotations

import fcntl
import os
import stat
from dataclasses import dataclass
from pathlib import Path

from fam_os.supervisor.audit_codec import (
    audit_record_digest_matches,
    create_audit_record,
    decode_audit_record,
    encode_audit_record,
)
from fam_os.supervisor.audit_contracts import (
    GENESIS_AUDIT_DIGEST,
    AuditChainVerification,
    SupervisorAuditIntent,
    SupervisorAuditRecord,
)
from fam_os.supervisor.errors import AuditEmissionError, AuditIntegrityError


@dataclass(frozen=True, slots=True)
class _ChainState:
    count: int
    head_digest: str
    event_ids: frozenset[str]


@dataclass(frozen=True, slots=True)
class _InvalidChain(Exception):
    sequence: int
    reason_code: str
    verified_count: int = 0
    head_digest: str = GENESIS_AUDIT_DIGEST


@dataclass(frozen=True, slots=True)
class JsonlHashChainAuditSink:
    path: Path
    max_line_bytes: int = 16_384

    def __post_init__(self) -> None:
        if not self.path.is_absolute() or "\0" in str(self.path):
            raise ValueError("audit path must be a safe absolute path")
        if self.max_line_bytes < 1024:
            raise ValueError("audit line limit is too small")

    def append(self, intent: SupervisorAuditIntent) -> SupervisorAuditRecord:
        try:
            fd = self._open(os.O_RDWR | os.O_CREAT | os.O_APPEND)
        except FileNotFoundError as error:
            raise AuditEmissionError("audit parent directory is absent") from error
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            state = _scan(fd, self.max_line_bytes)
            if intent.event_id in state.event_ids:
                raise _InvalidChain(
                    state.count + 1, "duplicate_event_id",
                    state.count, state.head_digest,
                )
            record = create_audit_record(intent, state.count + 1, state.head_digest)
            encoded = encode_audit_record(record)
            _require_line_size(encoded, self.max_line_bytes, record.sequence)
            written = os.write(fd, encoded + b"\n")
            if written != len(encoded) + 1:
                raise OSError("short audit write")
            os.fsync(fd)
            return record
        except _InvalidChain as error:
            raise AuditIntegrityError(
                f"audit chain {error.reason_code} at sequence {error.sequence}"
            ) from error
        except AuditIntegrityError:
            raise
        except (OSError, ValueError) as error:
            raise AuditEmissionError("required audit append failed") from error
        finally:
            os.close(fd)

    def verify(self) -> AuditChainVerification:
        try:
            fd = self._open(os.O_RDONLY)
        except FileNotFoundError:
            return AuditChainVerification(True, 0, GENESIS_AUDIT_DIGEST)
        try:
            fcntl.flock(fd, fcntl.LOCK_SH)
            state = _scan(fd, self.max_line_bytes)
            return AuditChainVerification(True, state.count, state.head_digest)
        except _InvalidChain as error:
            return AuditChainVerification(
                False, error.verified_count, error.head_digest,
                error.sequence, error.reason_code,
            )
        except (OSError, ValueError) as error:
            raise AuditEmissionError("audit verification failed") from error
        finally:
            os.close(fd)

    def _open(self, flags: int) -> int:
        no_follow = getattr(os, "O_NOFOLLOW", 0)
        _require_secure_parent(self.path.parent)
        try:
            fd = os.open(self.path, flags | os.O_CLOEXEC | no_follow, 0o600)
        except FileNotFoundError:
            raise
        except OSError as error:
            raise AuditEmissionError("audit file could not be opened") from error
        try:
            _require_secure_regular_file(fd)
        except Exception:
            os.close(fd)
            raise
        return fd


def _scan(fd: int, max_line_bytes: int) -> _ChainState:
    os.lseek(fd, 0, os.SEEK_SET)
    expected_sequence = 1
    previous_digest = GENESIS_AUDIT_DIGEST
    event_ids: set[str] = set()
    with os.fdopen(os.dup(fd), "rb") as stream:
        while line := stream.readline(max_line_bytes + 2):
            try:
                _require_line_size(line, max_line_bytes + 1, expected_sequence)
                if not line.endswith(b"\n"):
                    raise _InvalidChain(expected_sequence, "unterminated_record")
                record = _decode(line[:-1], expected_sequence)
                _require_link(record, expected_sequence, previous_digest)
                if record.intent.event_id in event_ids:
                    raise _InvalidChain(expected_sequence, "duplicate_event_id")
            except _InvalidChain as error:
                raise _InvalidChain(
                    error.sequence, error.reason_code,
                    expected_sequence - 1, previous_digest,
                ) from error
            previous_digest = record.digest
            event_ids.add(record.intent.event_id)
            expected_sequence += 1
    return _ChainState(
        expected_sequence - 1, previous_digest, frozenset(event_ids)
    )


def _decode(encoded: bytes, sequence: int) -> SupervisorAuditRecord:
    try:
        return decode_audit_record(encoded)
    except ValueError as error:
        raise _InvalidChain(sequence, "invalid_record") from error


def _require_link(
    record: SupervisorAuditRecord, sequence: int, previous_digest: str
) -> None:
    if record.sequence != sequence:
        raise _InvalidChain(sequence, "sequence_mismatch")
    if record.previous_digest != previous_digest:
        raise _InvalidChain(sequence, "previous_digest_mismatch")
    if not audit_record_digest_matches(record):
        raise _InvalidChain(sequence, "digest_mismatch")


def _require_line_size(encoded: bytes, maximum: int, sequence: int) -> None:
    if len(encoded) > maximum:
        raise _InvalidChain(sequence, "record_too_large")


def _require_secure_regular_file(fd: int) -> None:
    metadata = os.fstat(fd)
    if not stat.S_ISREG(metadata.st_mode):
        raise AuditEmissionError("audit target is not a regular file")
    if metadata.st_uid != os.geteuid() or stat.S_IMODE(metadata.st_mode) & 0o077:
        raise AuditEmissionError("audit file ownership or permissions are unsafe")


def _require_secure_parent(path: Path) -> None:
    try:
        metadata = path.lstat()
    except OSError as error:
        raise AuditEmissionError("audit parent directory is unavailable") from error
    unsafe_mode = stat.S_IMODE(metadata.st_mode) & 0o022
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or metadata.st_uid != os.geteuid()
        or unsafe_mode
    ):
        raise AuditEmissionError("audit parent directory is unsafe")
