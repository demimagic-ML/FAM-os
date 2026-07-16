"""Thread-safe Core request broker for live local application connectors."""

from dataclasses import dataclass
from threading import Condition
from time import monotonic
from uuid import uuid4

from fam_os.applications import ActionProposal, ActionResult, ObservationResult
from fam_os.applications.transport.codec import contract_message
from fam_os.applications.transport.dispatch import RegistryMessageDispatcher
from fam_os.applications.transport.wire import LocalMessageKind


@dataclass(slots=True)
class _Pending:
    value: object | None = None
    error: object | None = None
    done: bool = False


class ConnectorRequestBroker:
    """Own live connections and correlate synchronous Core-side operations."""

    def __init__(self, registry, timeout_seconds=30.0, id_factory=None):
        if timeout_seconds <= 0:
            raise ValueError("connector request timeout must be positive")
        self.registry = registry
        self.timeout_seconds = timeout_seconds
        self.id_factory = id_factory or (lambda: str(uuid4()))
        self._dispatcher = RegistryMessageDispatcher(registry, self)
        self._connections = {}
        self._sessions = {}
        self._pending = {}
        self._condition = Condition()

    def connected(self, connection) -> None:
        with self._condition:
            self._sessions[connection.session.session_id] = connection

    def dispatch(self, session, message):
        response = self._dispatcher.dispatch(session, message)
        if message.kind is LocalMessageKind.REGISTER:
            with self._condition:
                connection = self._sessions.get(session.session_id)
                if connection is None:
                    raise RuntimeError("connector connection is unavailable")
                self._connections[session.connector_id] = connection
                self._condition.notify_all()
        return response

    def disconnected(self, session, pending_request_ids) -> None:
        self._dispatcher.disconnected(session, pending_request_ids)
        with self._condition:
            self._sessions.pop(session.session_id, None)
            if session.connector_id is not None:
                self._connections.pop(session.connector_id, None)
            self._condition.notify_all()

    def received(self, session, correlation_id, value) -> None:
        self._complete(correlation_id, value=value)

    def transport_error(self, session, correlation_id, payload) -> None:
        self._complete(correlation_id, error=payload)

    def await_connector(self, connector_id: str, timeout_seconds=None) -> bool:
        deadline = monotonic() + (timeout_seconds or self.timeout_seconds)
        with self._condition:
            while connector_id not in self._connections:
                remaining = deadline - monotonic()
                if remaining <= 0:
                    return False
                self._condition.wait(remaining)
            return True

    def observe(self, connector_id, request) -> ObservationResult:
        return self._exchange(
            connector_id, LocalMessageKind.OBSERVE, request, ObservationResult,
        )

    def prepare_action(self, connector_id, request) -> ActionProposal:
        return self._exchange(
            connector_id, LocalMessageKind.PREPARE_ACTION, request, ActionProposal,
        )

    def execute_action(self, connector_id, confirmation) -> ActionResult:
        return self._exchange(
            connector_id, LocalMessageKind.CONFIRM_ACTION, confirmation, ActionResult,
        )

    def _exchange(self, connector_id, kind, value, expected_type):
        request_id = self.id_factory()
        pending = _Pending()
        with self._condition:
            connection = self._connections.get(connector_id)
            if connection is None:
                raise RuntimeError("application connector is unavailable")
            self._pending[request_id] = pending
        try:
            connection.send_request(contract_message(request_id, kind, value))
            result = self._wait(request_id, pending)
        except BaseException:
            with self._condition:
                self._pending.pop(request_id, None)
            raise
        if not isinstance(result, expected_type):
            raise RuntimeError("application connector returned the wrong result type")
        return result

    def _wait(self, request_id, pending):
        deadline = monotonic() + self.timeout_seconds
        with self._condition:
            while not pending.done:
                remaining = deadline - monotonic()
                if remaining <= 0:
                    self._pending.pop(request_id, None)
                    raise TimeoutError("application connector request timed out")
                self._condition.wait(remaining)
            self._pending.pop(request_id, None)
        if pending.error is not None:
            raise RuntimeError("application connector request failed")
        return pending.value

    def _complete(self, correlation_id, *, value=None, error=None):
        with self._condition:
            pending = self._pending.get(correlation_id)
            if pending is None:
                return
            pending.value = value
            pending.error = error
            pending.done = True
            self._condition.notify_all()
