"""Strict provider-neutral local Application Fabric wire envelope."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from fam_os.applications.identifiers import require_identifier
from fam_os.applications.payloads import JsonObject, freeze_payload


LOCAL_TRANSPORT_VERSION = "fam.applications.local/v1alpha1"


class LocalMessageKind(StrEnum):
    REGISTER = "register"
    OBSERVE = "observe"
    OBSERVATION = "observation"
    PREPARE_ACTION = "prepare_action"
    ACTION_PROPOSAL = "action_proposal"
    CONFIRM_ACTION = "confirm_action"
    ACTION_RESULT = "action_result"
    CONNECTOR_EVENT = "connector_event"
    CANCEL = "cancel"
    ACK = "ack"
    ERROR = "error"


RESPONSE_KINDS = {
    LocalMessageKind.OBSERVATION,
    LocalMessageKind.ACTION_PROPOSAL,
    LocalMessageKind.ACTION_RESULT,
    LocalMessageKind.ACK,
    LocalMessageKind.ERROR,
}

REQUEST_RESPONSE_KINDS = {
    LocalMessageKind.OBSERVE: LocalMessageKind.OBSERVATION,
    LocalMessageKind.PREPARE_ACTION: LocalMessageKind.ACTION_PROPOSAL,
    LocalMessageKind.CONFIRM_ACTION: LocalMessageKind.ACTION_RESULT,
}


@dataclass(frozen=True, slots=True)
class LocalMessage:
    message_id: str
    kind: LocalMessageKind
    payload: JsonObject = field(default_factory=dict)
    correlation_id: str | None = None
    contract_version: str = LOCAL_TRANSPORT_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "message_id", require_identifier(self.message_id, "message_id"))
        if not isinstance(self.kind, LocalMessageKind):
            raise ValueError("local message kind is invalid")
        if self.contract_version != LOCAL_TRANSPORT_VERSION:
            raise ValueError("unsupported local transport version")
        object.__setattr__(self, "payload", freeze_payload(self.payload))
        if self.correlation_id is not None:
            object.__setattr__(
                self, "correlation_id",
                require_identifier(self.correlation_id, "correlation_id"),
            )
        if self.kind in RESPONSE_KINDS and self.correlation_id is None:
            raise ValueError("response messages require correlation_id")
        if self.kind not in RESPONSE_KINDS and self.correlation_id is not None:
            raise ValueError("request/event messages cannot carry correlation_id")


def message_document(message: LocalMessage) -> dict[str, Any]:
    return {
        "contract_version": message.contract_version,
        "message_id": message.message_id,
        "kind": message.kind.value,
        "correlation_id": message.correlation_id,
        "payload": _thaw(message.payload),
    }


def message_from_document(document: Mapping[str, Any]) -> LocalMessage:
    expected = {"contract_version", "message_id", "kind", "correlation_id", "payload"}
    if not isinstance(document, dict) or set(document) != expected:
        raise ValueError("local message fields must match exactly")
    try:
        kind = LocalMessageKind(document["kind"])
    except (TypeError, ValueError) as error:
        raise ValueError("local message kind is invalid") from error
    if not isinstance(document["payload"], dict):
        raise ValueError("local message payload must be an object")
    return LocalMessage(
        document["message_id"], kind, document["payload"],
        document["correlation_id"], document["contract_version"],
    )


def _thaw(value):
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value
