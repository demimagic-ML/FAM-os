"""Validation for stable Application Fabric identifiers."""

from __future__ import annotations

import re


_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


def require_identifier(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not _IDENTIFIER.fullmatch(normalized):
        raise ValueError(
            f"{field_name} must be a non-empty identifier containing only "
            "letters, numbers, '.', '_', ':', or '-'"
        )
    return normalized


def require_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized


def normalize_unique(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    normalized = tuple(require_text(value, field_name) for value in values)
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{field_name} must be unique")
    return normalized
