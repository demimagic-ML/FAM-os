"""Private append-only SHA-256 chain for application-action audit events."""

import fcntl
import os
import stat
from dataclasses import dataclass
from pathlib import Path

from fam_os.applications import (
    ApplicationActionAuditIntent, ApplicationActionAuditRecord,
    ApplicationActionAuditVerification, ApplicationAuditEmissionError,
    ApplicationAuditIntegrityError,
)
from fam_os.applications.action_audit import GENESIS_ACTION_AUDIT_DIGEST
from fam_os.applications.action_audit_codec import (
    action_audit_record_digest_matches, create_action_audit_record,
    decode_action_audit_record, encode_action_audit_record,
)


@dataclass(frozen=True, slots=True)
class _State:
    count: int
    head: str
    event_ids: frozenset[str]


@dataclass(frozen=True, slots=True)
class _Invalid(Exception):
    sequence: int
    reason: str
    verified: int = 0
    head: str = GENESIS_ACTION_AUDIT_DIGEST


@dataclass(frozen=True, slots=True)
class ApplicationJsonlAuditSink:
    path: Path
    max_line_bytes: int = 16_384

    def __post_init__(self) -> None:
        if not self.path.is_absolute() or "\0" in str(self.path):
            raise ValueError("application audit path must be safe and absolute")
        if self.max_line_bytes < 1024:
            raise ValueError("application audit line bound is too small")

    def append(self, intent: ApplicationActionAuditIntent) -> ApplicationActionAuditRecord:
        try:
            fd = self._open(os.O_RDWR | os.O_CREAT | os.O_APPEND)
        except FileNotFoundError as error:
            raise ApplicationAuditEmissionError("application audit parent is absent") from error
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            state = _scan(fd, self.max_line_bytes)
            if intent.event_id in state.event_ids:
                raise _Invalid(state.count + 1, "duplicate_event_id", state.count, state.head)
            record = create_action_audit_record(intent, state.count + 1, state.head)
            encoded = encode_action_audit_record(record)
            _require_line(encoded, self.max_line_bytes, record.sequence)
            if os.write(fd, encoded + b"\n") != len(encoded) + 1:
                raise OSError("short application audit write")
            os.fsync(fd)
            return record
        except _Invalid as error:
            raise ApplicationAuditIntegrityError(
                f"application audit {error.reason} at sequence {error.sequence}"
            ) from error
        except ApplicationAuditIntegrityError:
            raise
        except (OSError, ValueError) as error:
            raise ApplicationAuditEmissionError("application audit append failed") from error
        finally:
            os.close(fd)

    def verify(self) -> ApplicationActionAuditVerification:
        try:
            fd = self._open(os.O_RDONLY)
        except FileNotFoundError:
            return ApplicationActionAuditVerification(True, 0, GENESIS_ACTION_AUDIT_DIGEST)
        try:
            fcntl.flock(fd, fcntl.LOCK_SH)
            state = _scan(fd, self.max_line_bytes)
            return ApplicationActionAuditVerification(True, state.count, state.head)
        except _Invalid as error:
            return ApplicationActionAuditVerification(
                False, error.verified, error.head, error.sequence, error.reason,
            )
        except (OSError, ValueError) as error:
            raise ApplicationAuditEmissionError("application audit verification failed") from error
        finally:
            os.close(fd)

    def _open(self, flags):
        _require_parent(self.path.parent)
        try:
            fd = os.open(
                self.path, flags | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0), 0o600,
            )
        except FileNotFoundError:
            raise
        except OSError as error:
            raise ApplicationAuditEmissionError("application audit open failed") from error
        try:
            _require_file(fd)
        except Exception:
            os.close(fd)
            raise
        return fd


def _scan(fd, maximum):
    os.lseek(fd, 0, os.SEEK_SET)
    sequence, previous, event_ids = 1, GENESIS_ACTION_AUDIT_DIGEST, set()
    with os.fdopen(os.dup(fd), "rb") as stream:
        while line := stream.readline(maximum + 2):
            try:
                _require_line(line, maximum + 1, sequence)
                if not line.endswith(b"\n"):
                    raise _Invalid(sequence, "unterminated_record")
                record = _decode(line[:-1], sequence)
                _require_link(record, sequence, previous, event_ids)
            except _Invalid as error:
                raise _Invalid(error.sequence, error.reason, sequence - 1, previous) from error
            previous = record.digest
            event_ids.add(record.intent.event_id)
            sequence += 1
    return _State(sequence - 1, previous, frozenset(event_ids))


def _decode(encoded, sequence):
    try:
        return decode_action_audit_record(encoded)
    except (UnicodeDecodeError, ValueError) as error:
        raise _Invalid(sequence, "invalid_record") from error


def _require_link(record, sequence, previous, event_ids):
    if record.sequence != sequence:
        raise _Invalid(sequence, "sequence_mismatch")
    if record.previous_digest != previous:
        raise _Invalid(sequence, "previous_digest_mismatch")
    if record.intent.event_id in event_ids:
        raise _Invalid(sequence, "duplicate_event_id")
    if not action_audit_record_digest_matches(record):
        raise _Invalid(sequence, "digest_mismatch")


def _require_line(encoded, maximum, sequence):
    if len(encoded) > maximum:
        raise _Invalid(sequence, "record_too_large")


def _require_file(fd):
    metadata = os.fstat(fd)
    if not stat.S_ISREG(metadata.st_mode):
        raise ApplicationAuditEmissionError("application audit target is not regular")
    if metadata.st_uid != os.geteuid() or stat.S_IMODE(metadata.st_mode) & 0o077:
        raise ApplicationAuditEmissionError("application audit file is not private")


def _require_parent(path):
    try:
        metadata = path.lstat()
    except OSError as error:
        raise ApplicationAuditEmissionError("application audit parent is unavailable") from error
    if not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != os.geteuid():
        raise ApplicationAuditEmissionError("application audit parent is unsafe")
    if stat.S_IMODE(metadata.st_mode) & 0o022:
        raise ApplicationAuditEmissionError("application audit parent is writable by others")
