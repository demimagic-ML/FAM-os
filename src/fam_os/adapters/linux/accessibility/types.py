"""Adapter-owned AT-SPI provider values."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProviderAccessibleAction:
    index: int
    name: str
    description: str | None = None
    key_binding: str | None = None


@dataclass(frozen=True, slots=True)
class ProviderAccessibleNode:
    process_id: int
    role: str
    name: str | None
    description: str | None
    states: tuple[str, ...]
    actions: tuple[ProviderAccessibleAction, ...]
    text: str | None
    protected: bool
    child_count: int
    text_truncated: bool = False
