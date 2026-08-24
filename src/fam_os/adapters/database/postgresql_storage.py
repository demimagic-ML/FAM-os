"""Private encrypted artifact storage for PostgreSQL verification backups."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from fam_os.adapters.database.sqlite_storage import private_directories
from fam_os.adapters.filesystem.candidate_io import fsync_directory


def retain_encrypted_postgresql_backup(
    root: Path,
    plaintext: bytes,
    protector,
    context: str,
    identity: str,
    maximum_bytes: int,
) -> tuple[Path, bytes]:
    """Encrypt before retention and create one private single-link artifact."""

    ciphertext = protector.encrypt(plaintext, context)
    if (
        not isinstance(ciphertext, bytes)
        or not ciphertext
        or ciphertext == plaintext
        or len(ciphertext) > maximum_bytes
    ):
        raise ValueError("PostgreSQL backup protection or size is invalid")
    directory = root / ".fam" / "database" / "backups"
    private_directories(root, directory)
    token = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
    target = directory / f"postgresql-{token}.enc"
    descriptor = os.open(
        target,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
        0o600,
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
