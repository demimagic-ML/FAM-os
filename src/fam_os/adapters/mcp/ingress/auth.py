"""One-time opaque bootstrap authentication for local MCP ingress sessions."""

import hashlib
import secrets
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Protocol

from fam_os.core.admission import RequestIdentity


class McpIngressAuthenticator(Protocol):
    def authenticate(self, token: str) -> RequestIdentity: ...


@dataclass(frozen=True, slots=True)
class _TokenRecord:
    identity: RequestIdentity
    expires_at: datetime


def _utc_now():
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class OneTimeMcpIngressTokens:
    clock: Callable[[], datetime] = _utc_now
    maximum_active: int = 1024
    _records: dict[str, _TokenRecord] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock)

    def __post_init__(self) -> None:
        if self.maximum_active <= 0:
            raise ValueError("MCP ingress token capacity must be positive")

    def issue(self, identity: RequestIdentity, expires_at: datetime) -> str:
        now = self.clock()
        if now.tzinfo is None:
            raise ValueError("MCP ingress token clock must be timezone-aware")
        if expires_at.tzinfo is None or expires_at <= now:
            raise ValueError("MCP ingress token expiry must be future and timezone-aware")
        token = secrets.token_urlsafe(32)
        digest = _digest(token)
        with self._lock:
            self._prune(now)
            if len(self._records) >= self.maximum_active:
                raise RuntimeError("MCP ingress token capacity is exhausted")
            self._records[digest] = _TokenRecord(identity, expires_at)
        return token

    def authenticate(self, token: str) -> RequestIdentity:
        if not isinstance(token, str) or len(token) < 32 or len(token) > 256:
            raise PermissionError("MCP ingress authentication failed")
        now = self.clock()
        if now.tzinfo is None:
            raise PermissionError("MCP ingress authentication failed")
        with self._lock:
            record = self._records.pop(_digest(token), None)
            self._prune(now)
        if record is None or record.expires_at <= now:
            raise PermissionError("MCP ingress authentication failed")
        return record.identity

    def _prune(self, now: datetime) -> None:
        expired = tuple(
            digest for digest, record in self._records.items()
            if record.expires_at <= now
        )
        for digest in expired:
            del self._records[digest]


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
