"""Authenticated connection, connector, correlation, and cancellation state."""

from dataclasses import dataclass, field
from threading import Lock

from fam_os.applications.identifiers import require_identifier
from fam_os.applications.transport.auth import UnixPeerCredentials


@dataclass(slots=True)
class LocalTransportSession:
    session_id: str
    peer: UnixPeerCredentials
    connector_id: str | None = None
    _pending: dict[str, str | None] = field(default_factory=dict)
    _cancelled: set[str] = field(default_factory=set)
    _lock: Lock = field(default_factory=Lock)

    def __post_init__(self) -> None:
        self.session_id = require_identifier(self.session_id, "session_id")

    def bind_connector(self, connector_id: str) -> None:
        connector_id = require_identifier(connector_id, "connector_id")
        with self._lock:
            if self.connector_id is not None and self.connector_id != connector_id:
                raise ValueError("session is already bound to another connector")
            self.connector_id = connector_id

    def begin(self, message_id: str, expected_response_kind: str | None = None) -> None:
        message_id = require_identifier(message_id, "message_id")
        with self._lock:
            if message_id in self._pending or message_id in self._cancelled:
                raise ValueError("message identity was already used in this session")
            self._pending[message_id] = expected_response_kind

    def complete(self, correlation_id: str) -> None:
        correlation_id = require_identifier(correlation_id, "correlation_id")
        with self._lock:
            if correlation_id not in self._pending:
                raise ValueError("response does not match a pending request")
            del self._pending[correlation_id]

    def require_pending(
        self, correlation_id: str, response_kind: str | None = None
    ) -> None:
        correlation_id = require_identifier(correlation_id, "correlation_id")
        with self._lock:
            if correlation_id not in self._pending:
                raise ValueError("response does not match a pending request")
            expected = self._pending[correlation_id]
            if response_kind is not None and expected not in (None, response_kind):
                raise ValueError("response kind does not match the pending request")

    def cancel(self, request_id: str) -> bool:
        request_id = require_identifier(request_id, "request_id")
        with self._lock:
            if request_id not in self._pending:
                return False
            del self._pending[request_id]
            self._cancelled.add(request_id)
            return True

    def cancelled(self, request_id: str) -> bool:
        with self._lock:
            return request_id in self._cancelled

    def close(self) -> tuple[str, ...]:
        with self._lock:
            pending = tuple(sorted(self._pending))
            self._pending.clear()
            return pending
