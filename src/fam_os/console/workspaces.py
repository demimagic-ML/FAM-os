"""Authenticated, bounded navigation of owner-local workspace directories."""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ConsoleWorkspaceApi:
    root: Path
    maximum_entries: int = 256

    def __post_init__(self) -> None:
        if not self.root.is_absolute() or not _owned_directory(self.root):
            raise ValueError("workspace root must be an owner directory")
        if not 1 <= self.maximum_entries <= 1024:
            raise ValueError("workspace entry bound is invalid")

    def browse(self, requested_path: str | None = None) -> dict[str, object]:
        path = self.root if requested_path is None else Path(requested_path)
        _require_scoped_directory(self.root, path)
        entries = sorted(
            (_entry(item) for item in os.scandir(path)),
            key=lambda item: (
                item["kind"] != "directory",
                str(item["name"]).casefold(),
                str(item["name"]),
            ),
        )
        visible = entries[:self.maximum_entries]
        parent = None if path == self.root else path.parent
        return {
            "root_path": str(self.root),
            "path": str(path),
            "uri": _uri(path, directory=True),
            "display_name": path.name or str(path),
            "parent_path": None if parent is None else str(parent),
            "entries": visible,
            "truncated": len(entries) > self.maximum_entries,
            "maximum_entries": self.maximum_entries,
        }


def _require_scoped_directory(root: Path, path: Path) -> None:
    if not path.is_absolute() or ".." in path.parts:
        raise PermissionError("workspace path is outside the owner scope")
    if path != root and not path.is_relative_to(root):
        raise PermissionError("workspace path is outside the owner scope")
    current = root
    if not _owned_directory(current):
        raise PermissionError("workspace root is no longer trusted")
    for part in path.relative_to(root).parts:
        current = current / part
        if not _owned_directory(current):
            raise PermissionError("workspace path is not an owner directory")


def _owned_directory(path: Path) -> bool:
    try:
        details = path.stat(follow_symlinks=False)
    except OSError:
        return False
    return (
        stat.S_ISDIR(details.st_mode)
        and not path.is_symlink()
        and details.st_uid == os.geteuid()
    )


def _entry(entry: os.DirEntry) -> dict[str, object]:
    path = Path(entry.path)
    if entry.is_symlink():
        kind = "symlink"
        size = None
    elif entry.is_dir(follow_symlinks=False):
        kind = "directory"
        size = None
    elif entry.is_file(follow_symlinks=False):
        kind = "file"
        size = entry.stat(follow_symlinks=False).st_size
    else:
        kind = "other"
        size = None
    return {
        "name": entry.name,
        "path": str(path),
        "uri": _uri(path, directory=kind == "directory"),
        "kind": kind,
        "size_bytes": size,
        "selectable": kind in {"directory", "file"},
    }


def _uri(path: Path, *, directory: bool) -> str:
    uri = path.as_uri()
    return uri + "/" if directory and not uri.endswith("/") else uri
