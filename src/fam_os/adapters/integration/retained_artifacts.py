"""Race-aware hashing of explicitly retained candidate artifacts."""

import hashlib
import os
from pathlib import Path

from fam_os.core.engineering import IntegrationRetainedArtifact


def capture_retained_artifacts(root: Path, paths, maximum_bytes: int):
    values = []
    consumed = 0
    for relative in paths:
        path = _confined_regular_file(root, relative)
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            before = os.fstat(descriptor)
            if not _regular(before.st_mode):
                raise PermissionError("retained artifact is not a regular file")
            consumed += before.st_size
            if consumed > maximum_bytes:
                raise PermissionError("retained artifacts exceed changed-byte budget")
            digest = hashlib.sha256()
            with os.fdopen(descriptor, "rb", closefd=False) as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            after = os.fstat(descriptor)
            if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
                after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns,
            ):
                raise RuntimeError("retained artifact changed while hashing")
        finally:
            os.close(descriptor)
        values.append(IntegrationRetainedArtifact(relative, digest.hexdigest()))
    return tuple(values)


def _confined_regular_file(root: Path, relative: str) -> Path:
    current = root
    for part in Path(relative).parts:
        current = current / part
        if current.is_symlink():
            raise PermissionError("retained artifact traverses a symbolic link")
    try:
        current.resolve(strict=True).relative_to(root.resolve(strict=True))
    except (FileNotFoundError, ValueError) as error:
        raise PermissionError("retained artifact is missing or escapes candidate") from error
    if Path(relative).parts[:2] == (".fam", "integration"):
        raise PermissionError("internal integration state cannot be retained")
    return current


def _regular(mode: int) -> bool:
    return (mode & 0o170000) == 0o100000
