"""Inward-facing ports for database backup protection and lifecycle control."""

from dataclasses import dataclass
from datetime import datetime
from collections.abc import Callable
from typing import Protocol

from fam_os.core.engineering._validation import aware, text


class DatabaseBackupProtector(Protocol):
    """Protect retained backups without exposing key material to the adapter."""

    def encrypt(self, plaintext: bytes, context: str) -> bytes: ...

    def decrypt(self, ciphertext: bytes, context: str) -> bytes: ...


class DatabaseExecutionControl(Protocol):
    """Live cancellation and revocation state checked across a mutation."""

    def cancelled(self) -> bool: ...

    def authorization_active(self) -> bool: ...


@dataclass(frozen=True, slots=True)
class DatabaseExecutionPermit:
    permit_id: str
    approved_changeset_id: str
    exact_host_id: str
    issued_at: datetime
    expires_at: datetime

    def __post_init__(self) -> None:
        for name in ("permit_id", "approved_changeset_id", "exact_host_id"):
            text(getattr(self, name), name)
        aware(self.issued_at, "issued_at")
        aware(self.expires_at, "expires_at")
        if self.expires_at <= self.issued_at:
            raise ValueError("database execution permit must expire after issue")

    def active_at(self, instant: datetime) -> bool:
        aware(instant, "instant")
        return self.issued_at <= instant < self.expires_at


class PermitBoundDatabaseControl:
    def __init__(
        self,
        control: DatabaseExecutionControl,
        permit: DatabaseExecutionPermit,
        clock: Callable[[], datetime],
    ) -> None:
        self._control = control
        self._permit = permit
        self._clock = clock

    def cancelled(self) -> bool:
        return self._control.cancelled()

    def authorization_active(self) -> bool:
        return (
            self._permit.active_at(self._clock())
            and self._control.authorization_active()
        )
