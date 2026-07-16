"""Typed registry and connector-result dispatch behind authenticated sessions."""

from dataclasses import dataclass
from typing import Protocol

from fam_os.applications import (
    ActionProposal, ActionResult, ApplicationCapabilityRegistry, ConnectorEvent,
    ConnectorEventKind, ConnectorRegistration, ObservationResult,
)
from fam_os.applications.transport.codec import decode_contract_message
from fam_os.applications.transport.wire import LocalMessage, LocalMessageKind


class ApplicationMessageConsumer(Protocol):
    def received(self, session, correlation_id: str, value: object) -> None: ...

    def transport_error(self, session, correlation_id: str, payload: object) -> None: ...


@dataclass(slots=True)
class RegistryMessageDispatcher:
    registry: ApplicationCapabilityRegistry
    consumer: ApplicationMessageConsumer

    def dispatch(self, session, message):
        if message.kind is LocalMessageKind.REGISTER:
            registration = decode_contract_message(message)
            if not isinstance(registration, ConnectorRegistration):
                raise ValueError("registration message has wrong contract type")
            if registration.connector_id != session.connector_id:
                raise PermissionError("registration connector does not match session")
            self.registry.register(registration)
            return _ack(message)
        if message.kind is LocalMessageKind.CONNECTOR_EVENT:
            event = decode_contract_message(message)
            if not isinstance(event, ConnectorEvent) or event.connector_id != session.connector_id:
                raise PermissionError("connector event does not match session")
            if event.kind is ConnectorEventKind.INSTANCE_CLOSED:
                self.registry.unregister(session.connector_id)
            return _ack(message)
        if message.kind in _RESULT_TYPES:
            value = decode_contract_message(message)
            if not isinstance(value, _RESULT_TYPES[message.kind]):
                raise ValueError("response message has wrong contract type")
            self.consumer.received(session, message.correlation_id, value)
            return None
        if message.kind is LocalMessageKind.ERROR:
            self.consumer.transport_error(
                session, message.correlation_id, message.payload
            )
            return None
        if message.kind is LocalMessageKind.CANCEL:
            return _ack(message)
        raise PermissionError("connector cannot initiate this message kind")

    def disconnected(self, session, pending_request_ids):
        if session.connector_id is not None:
            self.registry.unregister(session.connector_id)
        for request_id in pending_request_ids:
            self.consumer.transport_error(
                session, request_id,
                {"code": "transport.disconnected", "safe_message": "Connector disconnected."},
            )


_RESULT_TYPES = {
    LocalMessageKind.OBSERVATION: ObservationResult,
    LocalMessageKind.ACTION_PROPOSAL: ActionProposal,
    LocalMessageKind.ACTION_RESULT: ActionResult,
}


def _ack(message):
    return LocalMessage(
        f"ack-{message.message_id}", LocalMessageKind.ACK, {}, message.message_id
    )
