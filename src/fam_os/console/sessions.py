"""Short-lived loopback Console sessions and CSRF protection."""

from __future__ import annotations

import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock


@dataclass(frozen=True, slots=True)
class ConsoleSession:
    session_id: str
    csrf_token: str
    expires_at: datetime


class ConsoleSessionStore:
    def __init__(self, bootstrap_token: str, lifetime: timedelta = timedelta(hours=8)):
        if len(bootstrap_token) < 32:
            raise ValueError("Console bootstrap token is too short")
        self._bootstrap = bootstrap_token
        self._lifetime = lifetime
        self._sessions: dict[str, ConsoleSession] = {}
        self._lock = Lock()

    def exchange(self, supplied: str) -> ConsoleSession | None:
        if not hmac.compare_digest(supplied, self._bootstrap):
            return None
        now = datetime.now(timezone.utc)
        session = ConsoleSession(
            f"console-{secrets.token_urlsafe(32)}",
            secrets.token_urlsafe(32),
            now + self._lifetime,
        )
        with self._lock:
            self._prune(now)
            self._sessions[session.session_id] = session
        return session

    def authenticate(self, session_id: str) -> ConsoleSession | None:
        now = datetime.now(timezone.utc)
        with self._lock:
            self._prune(now)
            return self._sessions.get(session_id)

    def validate_mutation(self, session_id: str, csrf_token: str) -> bool:
        session = self.authenticate(session_id)
        return session is not None and hmac.compare_digest(session.csrf_token, csrf_token)

    def revoke(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)

    def _prune(self, now: datetime) -> None:
        expired = tuple(
            key for key, value in self._sessions.items() if value.expires_at <= now
        )
        for key in expired:
            self._sessions.pop(key, None)
