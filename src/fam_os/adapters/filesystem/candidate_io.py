"""Low-level no-symlink I/O for engineering candidate workspaces."""

from __future__ import annotations

import hashlib
import os
import shutil
import stat
import tempfile
from pathlib import Path


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def read_regular(path: Path, maximum_bytes: int) -> bytes:
    descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        details = os.fstat(descriptor)
        if not stat.S_ISREG(details.st_mode) or details.st_size > maximum_bytes:
            raise ValueError("candidate entry is not a bounded regular file")
        chunks: list[bytes] = []
        size = 0
        while True:
            chunk = os.read(descriptor, min(65_536, maximum_bytes + 1 - size))
            if not chunk:
                return b"".join(chunks)
            chunks.append(chunk)
            size += len(chunk)
            if size > maximum_bytes:
                raise ValueError("candidate entry exceeds its byte bound")
    finally:
        os.close(descriptor)


def reject_tree_symlinks(
    root: Path, excluded_directories: frozenset[str] = frozenset(),
) -> None:
    if not root.is_absolute() or not root.is_dir() or root.is_symlink():
        raise ValueError("workspace root must be a real absolute directory")
    for current, directories, files in os.walk(root, followlinks=False):
        current_path = Path(current)
        directories[:] = sorted(
            name for name in directories if name not in excluded_directories
        )
        for name in directories + files:
            path = current_path / name
            if path.is_symlink():
                raise PermissionError("workspace trees cannot contain symbolic links")
            details = path.stat(follow_symlinks=False)
            if stat.S_ISREG(details.st_mode) and details.st_nlink != 1:
                raise PermissionError("workspace trees cannot contain hardlinked files")


def contained(root: Path, relative: str, *, missing_leaf: bool = False) -> Path:
    candidate = root / relative
    if not candidate.is_relative_to(root) or ".." in Path(relative).parts:
        raise PermissionError("candidate path escapes its workspace")
    current = root
    parts = Path(relative).parts
    for index, part in enumerate(parts):
        current /= part
        try:
            details = current.lstat()
        except FileNotFoundError:
            if missing_leaf and index == len(parts) - 1:
                return candidate
            if missing_leaf and not current.exists():
                continue
            raise
        if stat.S_ISLNK(details.st_mode):
            raise PermissionError("candidate path traverses a symbolic link")
    return candidate


def atomic_write(path: Path, content: bytes, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".fam-candidate-", dir=path.parent)
    try:
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        fsync_directory(path.parent)
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def clone_regular(source: Path, target: Path) -> str:
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        import fcntl
        source_descriptor = os.open(source, os.O_RDONLY | os.O_NOFOLLOW)
        target_descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            fcntl.ioctl(target_descriptor, 0x40049409, source_descriptor)
            strategy = "reflink"
        finally:
            os.close(source_descriptor)
            os.close(target_descriptor)
    except OSError:
        try:
            target.unlink()
        except FileNotFoundError:
            pass
        shutil.copyfile(source, target, follow_symlinks=False)
        strategy = "full_copy_fallback"
    os.chmod(target, stat.S_IMODE(source.stat(follow_symlinks=False).st_mode))
    return strategy


def fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def remove_owned(path: Path) -> None:
    if path.is_symlink():
        raise PermissionError("refusing to remove a symbolic link")
    if path.is_dir():
        path.rmdir()
    elif path.exists():
        path.unlink()
