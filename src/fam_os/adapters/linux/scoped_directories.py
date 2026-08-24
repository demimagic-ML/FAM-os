"""Descriptor-relative create and empty-directory reversal within owner roots."""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ScopedDirectoryPolicy:
    roots: tuple[Path, ...]

    def __post_init__(self) -> None:
        if not self.roots or len(set(self.roots)) != len(self.roots):
            raise ValueError("directory policy requires unique roots")
        for root in self.roots:
            if not root.is_absolute() or not root.is_dir() or root.is_symlink():
                raise ValueError("directory roots must be real absolute directories")

    def root_for(self, path: Path) -> Path:
        if not path.is_absolute() or ".." in path.parts:
            raise PermissionError("directory path is outside the approved scope")
        root = next((item for item in self.roots if path.is_relative_to(item)), None)
        if root is None or path == root:
            raise PermissionError("directory path is outside the approved scope")
        return root


@dataclass(frozen=True, slots=True)
class DirectoryObservation:
    path: str
    exists: bool
    empty: bool | None
    device: int | None
    inode: int | None

    @property
    def revision(self) -> str:
        if not self.exists:
            return "directory:absent"
        return f"directory:{self.device}:{self.inode}"


@dataclass(frozen=True, slots=True)
class DirectoryEntryObservation:
    name: str
    kind: str
    size_bytes: int | None


@dataclass(frozen=True, slots=True)
class DirectoryListing:
    path: str
    entries: tuple[DirectoryEntryObservation, ...]
    truncated: bool
    maximum_entries: int


@dataclass(frozen=True, slots=True)
class DirectoryCreateProposal:
    operation_id: str
    path: str


@dataclass(frozen=True, slots=True)
class DirectoryRemovalProposal:
    operation_id: str
    path: str
    expected_device: int
    expected_inode: int


class ScopedDirectoryAdapter:
    def __init__(self, policy: ScopedDirectoryPolicy) -> None:
        self.policy = policy

    def observe(self, path: Path) -> DirectoryObservation:
        if path in self.policy.roots:
            target = _open_directory(self.policy, path)
            try:
                details = os.fstat(target)
                return DirectoryObservation(
                    str(path), True, len(os.listdir(target)) == 0,
                    details.st_dev, details.st_ino,
                )
            finally:
                os.close(target)
        parent, name = _open_parent(self.policy, path)
        try:
            try:
                target = os.open(
                    name, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
                    dir_fd=parent,
                )
            except FileNotFoundError:
                return DirectoryObservation(str(path), False, None, None, None)
            try:
                details = os.fstat(target)
                if not stat.S_ISDIR(details.st_mode):
                    raise ValueError("directory target is not a directory")
                return DirectoryObservation(
                    str(path), True, len(os.listdir(target)) == 0,
                    details.st_dev, details.st_ino,
                )
            finally:
                os.close(target)
        finally:
            os.close(parent)

    def list_entries(
        self, path: Path, maximum_entries: int = 256,
    ) -> DirectoryListing:
        if maximum_entries <= 0 or maximum_entries > 1024:
            raise ValueError("directory listing bound is invalid")
        target = _open_directory(self.policy, path)
        try:
            entries = sorted(
                (_entry(item) for item in os.scandir(target)),
                key=lambda item: (item.kind != "directory", item.name.casefold(), item.name),
            )
        finally:
            os.close(target)
        return DirectoryListing(
            str(path), tuple(entries[:maximum_entries]),
            len(entries) > maximum_entries, maximum_entries,
        )

    def prepare_create(self, operation_id: str, path: Path) -> DirectoryCreateProposal:
        observed = self.observe(path)
        if observed.exists:
            raise FileExistsError("directory target already exists")
        return DirectoryCreateProposal(operation_id, str(path))

    def create(self, proposal: DirectoryCreateProposal) -> DirectoryObservation:
        path = Path(proposal.path)
        if self.observe(path).exists:
            raise FileExistsError("directory target already exists")
        parent, name = _open_parent(self.policy, path)
        try:
            os.mkdir(name, mode=0o700, dir_fd=parent)
            os.fsync(parent)
        finally:
            os.close(parent)
        observed = self.observe(path)
        if not observed.exists or observed.empty is not True:
            raise RuntimeError("created directory postcondition failed")
        return observed

    def prepare_remove(
        self, operation_id: str, path: Path, expected_device: int, expected_inode: int,
    ) -> DirectoryRemovalProposal:
        observed = self.observe(path)
        if not _matches_empty(observed, expected_device, expected_inode):
            raise RuntimeError("directory reversal precondition changed")
        return DirectoryRemovalProposal(
            operation_id, str(path), expected_device, expected_inode,
        )

    def remove_empty(self, proposal: DirectoryRemovalProposal) -> DirectoryObservation:
        path = Path(proposal.path)
        observed = self.observe(path)
        if not _matches_empty(
            observed, proposal.expected_device, proposal.expected_inode,
        ):
            raise RuntimeError("directory reversal precondition changed")
        parent, name = _open_parent(self.policy, path)
        try:
            details = os.stat(name, dir_fd=parent, follow_symlinks=False)
            if (
                not stat.S_ISDIR(details.st_mode)
                or details.st_dev != proposal.expected_device
                or details.st_ino != proposal.expected_inode
            ):
                raise RuntimeError("directory reversal identity changed")
            os.rmdir(name, dir_fd=parent)
            os.fsync(parent)
        finally:
            os.close(parent)
        result = self.observe(path)
        if result.exists:
            raise RuntimeError("directory reversal postcondition failed")
        return result


def _matches_empty(observed, expected_device, expected_inode) -> bool:
    return (
        observed.exists and observed.empty is True
        and observed.device == expected_device and observed.inode == expected_inode
    )


def _open_parent(policy: ScopedDirectoryPolicy, path: Path) -> tuple[int, str]:
    root = policy.root_for(path)
    relative = path.relative_to(root)
    parts = relative.parts
    if not parts or not parts[-1] or parts[-1] in {".", ".."}:
        raise PermissionError("directory target name is invalid")
    descriptor = os.open(
        root, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
    )
    try:
        for part in parts[:-1]:
            child = os.open(
                part, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
                dir_fd=descriptor,
            )
            os.close(descriptor)
            descriptor = child
        return descriptor, parts[-1]
    except BaseException:
        os.close(descriptor)
        raise


def _open_directory(policy: ScopedDirectoryPolicy, path: Path) -> int:
    if not path.is_absolute() or ".." in path.parts:
        raise PermissionError("directory path is outside the approved scope")
    root = next(
        (item for item in policy.roots if path == item or path.is_relative_to(item)),
        None,
    )
    if root is None:
        raise PermissionError("directory path is outside the approved scope")
    descriptor = os.open(
        root, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
    )
    try:
        for part in path.relative_to(root).parts:
            child = os.open(
                part, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
                dir_fd=descriptor,
            )
            os.close(descriptor)
            descriptor = child
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _entry(entry: os.DirEntry) -> DirectoryEntryObservation:
    if entry.is_symlink():
        return DirectoryEntryObservation(entry.name, "symlink", None)
    if entry.is_dir(follow_symlinks=False):
        return DirectoryEntryObservation(entry.name, "directory", None)
    if entry.is_file(follow_symlinks=False):
        return DirectoryEntryObservation(
            entry.name, "file", entry.stat(follow_symlinks=False).st_size,
        )
    return DirectoryEntryObservation(entry.name, "other", None)
