"""Atomic in-memory replay protection for confirmations."""

from dataclasses import dataclass, field
from threading import Lock


@dataclass(slots=True)
class InMemoryConfirmationReplayRegistry:
    _confirmation_ids: set[str] = field(default_factory=set)
    _lock: Lock = field(default_factory=Lock)

    def reserve(self, confirmation_id: str) -> bool:
        with self._lock:
            if confirmation_id in self._confirmation_ids:
                return False
            self._confirmation_ids.add(confirmation_id)
            return True
