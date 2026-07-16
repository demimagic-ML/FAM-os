"""Replay boundary for user confirmation evidence."""

from typing import Protocol


class ConfirmationReplayRegistry(Protocol):
    def reserve(self, confirmation_id: str) -> bool: ...
