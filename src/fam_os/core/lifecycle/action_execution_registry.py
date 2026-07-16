"""Process-local atomic replay protection for application action execution."""

from dataclasses import dataclass, field
from threading import Lock


@dataclass(slots=True)
class InMemoryActionExecutionReplayRegistry:
    _identifiers: set[str] = field(default_factory=set)
    _lock: Lock = field(default_factory=Lock)

    def reserve(self, confirmation_id: str) -> bool:
        with self._lock:
            if confirmation_id in self._identifiers:
                return False
            self._identifiers.add(confirmation_id)
            return True
