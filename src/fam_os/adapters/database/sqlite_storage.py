"""Private candidate storage and encrypted SQLite snapshot operations."""

from __future__ import annotations

import hashlib
import os
import sqlite3
import stat
import tempfile
from pathlib import Path

from fam_os.adapters.filesystem.candidate_io import contained, fsync_directory
from fam_os.core.engineering.database_ports import DatabaseBackupProtector


def secure_database_path(root: Path, relative: str) -> Path:
    resolved_root = root.resolve(strict=True)
    if root != resolved_root or root.is_symlink() or not root.is_dir():
        raise PermissionError("database candidate root must be a real absolute directory")
    target = contained(root, relative)
    details = target.stat(follow_symlinks=False)
    if not stat.S_ISREG(details.st_mode) or details.st_nlink != 1:
        raise PermissionError("candidate database must be a single-link regular file")
    return target


def encrypted_snapshot(
    source: sqlite3.Connection,
    root: Path,
    backup_id: str,
    protector: DatabaseBackupProtector,
    context: str,
) -> tuple[Path, bytes]:
    directory = root / ".fam" / "database" / "backups"
    private_directories(root, directory)
    plaintext = _snapshot_bytes(source, directory)
    ciphertext = protector.encrypt(plaintext, context)
    if not ciphertext or ciphertext == plaintext:
        raise ValueError("database backup protector returned unprotected content")
    target = directory / f"{backup_id}.enc"
    descriptor = os.open(
        target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600,
    )
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(ciphertext)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    fsync_directory(directory)
    return target, ciphertext


def decrypt_snapshot(
    artifact: Path,
    protector: DatabaseBackupProtector,
    context: str,
    expected_sha256: str | None = None,
    expected_size: int | None = None,
) -> bytes:
    descriptor = os.open(artifact, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        details = os.fstat(descriptor)
        if not stat.S_ISREG(details.st_mode) or details.st_nlink != 1:
            raise PermissionError("database backup artifact is unsafe")
        ciphertext = b""
        while chunk := os.read(descriptor, 65_536):
            ciphertext += chunk
    finally:
        os.close(descriptor)
    if expected_size is not None and len(ciphertext) != expected_size:
        raise RuntimeError("database backup size does not match its receipt")
    if expected_sha256 is not None and artifact_digest(ciphertext) != expected_sha256:
        raise RuntimeError("database backup digest does not match its receipt")
    return protector.decrypt(ciphertext, context)


def open_snapshot(content: bytes, directory: Path) -> tuple[sqlite3.Connection, Path]:
    descriptor, name = tempfile.mkstemp(prefix=".fam-restore-", dir=directory)
    path = Path(name)
    try:
        os.fchmod(descriptor, 0o600)
        os.write(descriptor, content)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return sqlite3.connect(path), path


def restore_snapshot(snapshot: sqlite3.Connection, target: sqlite3.Connection) -> None:
    snapshot.backup(target)
    if target.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise RuntimeError("restored database failed integrity verification")


def artifact_digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _snapshot_bytes(source: sqlite3.Connection, directory: Path) -> bytes:
    descriptor, name = tempfile.mkstemp(prefix=".fam-backup-", dir=directory)
    os.close(descriptor)
    path = Path(name)
    target = sqlite3.connect(path)
    try:
        source.backup(target)
        target.close()
        return path.read_bytes()
    finally:
        try:
            target.close()
        finally:
            path.unlink(missing_ok=True)


def private_directories(root: Path, target: Path) -> None:
    current = root
    for part in target.relative_to(root).parts:
        current /= part
        if current.exists() and current.is_symlink():
            raise PermissionError("database artifact path contains a symlink")
        current.mkdir(mode=0o700, exist_ok=True)
        os.chmod(current, 0o700)
