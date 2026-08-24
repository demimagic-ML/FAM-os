"""Small invariant validators for engineering contract modules."""

from datetime import datetime
from pathlib import PurePosixPath


def text(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be nonempty")


def texts(values: tuple[str, ...], name: str, *, unique: bool = True) -> None:
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise ValueError(f"{name} must contain only nonempty strings")
    if unique and len(set(values)) != len(values):
        raise ValueError(f"{name} must not contain duplicates")


def aware(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")


def digest(value: str | None, name: str, *, required: bool = False) -> None:
    if value is None:
        if required:
            raise ValueError(f"{name} is required")
        return
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")


def absolute_path(value: str, name: str) -> None:
    text(value, name)
    path = PurePosixPath(value)
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError(f"{name} must be an absolute normalized path")


def relative_path(value: str, name: str) -> None:
    text(value, name)
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or value in {".", "./"}:
        raise ValueError(f"{name} must be a normalized workspace-relative path")


def positive(value: int, name: str, *, allow_zero: bool = False) -> None:
    minimum = 0 if allow_zero else 1
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        qualifier = "nonnegative" if allow_zero else "positive"
        raise ValueError(f"{name} must be a {qualifier} integer")


def unique_enum(values: tuple[object, ...], name: str) -> None:
    if len(set(values)) != len(values):
        raise ValueError(f"{name} must not contain duplicates")
