"""Authenticated local connection state and message dispatch."""

from collections.abc import Callable
from dataclasses import dataclass
from uuid import uuid4

from fam_os.applications.transport.auth import (
    PeerAuthorizationPolicy, unix_peer_credentials,
)
from fam_os.applications.transport.framing import receive_frame, send_frame
from fam_os.applications.transport.ports import LocalMessageDispatcher
from fam_os.applications.transport.session import LocalTransportSession
from fam_os.applications.transport.wire import (
    REQUEST_RESPONSE_KINDS, RESPONSE_KINDS, LocalMessage, LocalMessageKind,
)


def _identifier() -> str:
    return str(uuid4())


@dataclass(slots=True)
class AuthenticatedLocalConnection:
    stream: object
    session: LocalTransportSession
    dispatcher: LocalMessageDispatcher
    message_id_factory: Callable[[], str] = _identifier

    @classmethod
    def authenticate(
        cls, stream, policy: PeerAuthorizationPolicy, dispatcher,
        session_id_factory: Callable[[], str] = _identifier,
        credential_reader=unix_peer_credentials,
    ):
        peer = credential_reader(stream)
        if not policy.authorize(peer):
            raise PermissionError("local peer is not authorized")
        return cls(stream, LocalTransportSession(session_id_factory(), peer), dispatcher)

    def process_next(self) -> bool:
        try:
            message = receive_frame(self.stream)
        except EOFError:
            return False
        self._validate_inbound(message)
        response = self.dispatcher.dispatch(self.session, message)
        if message.kind in RESPONSE_KINDS:
            self.session.complete(message.correlation_id)
        if response is not None:
            if response.correlation_id != message.message_id:
                raise ValueError("dispatcher response must correlate to inbound message")
            send_frame(self.stream, response)
        return True

    def send_request(self, message: LocalMessage) -> None:
        if message.kind not in REQUEST_RESPONSE_KINDS:
            raise ValueError("message is not a Core connector request")
        if self.session.connector_id is None:
            raise ValueError("connection has no bound connector")
        expected = REQUEST_RESPONSE_KINDS[message.kind]
        self.session.begin(message.message_id, expected.value)
        send_frame(self.stream, message)

    def cancel_request(self, request_id: str, cancellation_id: str) -> None:
        if self.session.connector_id is None:
            raise ValueError("connection has no bound connector")
        if not self.session.cancel(request_id):
            raise ValueError("cancellation does not match a pending request")
        send_frame(self.stream, LocalMessage(
            cancellation_id, LocalMessageKind.CANCEL, {"request_id": request_id}
        ))

    def close(self) -> None:
        pending = self.session.close()
        try:
            self.dispatcher.disconnected(self.session, pending)
        finally:
            self.stream.close()

    def _validate_inbound(self, message) -> None:
        if message.kind is LocalMessageKind.REGISTER:
            body = message.payload.get("payload")
            connector_id = body.get("connector_id") if hasattr(body, "get") else None
            if not isinstance(connector_id, str):
                raise ValueError("registration message requires connector_id")
            self.session.bind_connector(connector_id)
            return
        if self.session.connector_id is None:
            raise PermissionError("connector must register before other messages")
        if message.kind in RESPONSE_KINDS:
            response_kind = None if message.kind is LocalMessageKind.ERROR else message.kind.value
            self.session.require_pending(message.correlation_id, response_kind)
        if message.kind is LocalMessageKind.CANCEL:
            request_id = message.payload.get("request_id")
            if not isinstance(request_id, str) or not self.session.cancel(request_id):
                raise ValueError("cancellation does not match a pending request")
