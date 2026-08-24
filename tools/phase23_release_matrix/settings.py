"""Validated inputs for one clean release-profile matrix."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .contracts import ReleaseProfile


@dataclass(frozen=True, slots=True)
class MatrixSettings:
    repository: Path
    python: Path
    output_root: Path
    run_id: str
    profiles: tuple[ReleaseProfile, ...]
    dependency_wheelhouse: Path | None = None
    code: Path = Path("/usr/bin/code")

    def __post_init__(self) -> None:
        if any(not path.is_absolute() for path in (
            self.repository, self.python, self.output_root, self.code,
        )):
            raise ValueError("release-matrix paths must be absolute")
        if not self.repository.is_dir() or self.repository.is_symlink():
            raise ValueError("release-matrix repository is unavailable or unsafe")
        if not self.python.is_file() or self.python.is_symlink():
            raise ValueError("release-matrix Python is unavailable or unsafe")
        if self.output_root.exists():
            raise ValueError("release-matrix output root must not already exist")
        if not self.run_id or any(
            character not in "abcdefghijklmnopqrstuvwxyz0123456789-"
            for character in self.run_id
        ):
            raise ValueError("release-matrix run identity is invalid")
        if not self.profiles:
            raise ValueError("release matrix requires at least one profile")
        if self.dependency_wheelhouse is not None and (
            not self.dependency_wheelhouse.is_dir()
            or self.dependency_wheelhouse.is_symlink()
        ):
            raise ValueError("dependency wheelhouse is unavailable or unsafe")
