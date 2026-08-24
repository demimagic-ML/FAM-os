"""Strict bounded JSON wire protocol between FAM Shell and local Core."""

import json
import struct
from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping

from fam_os.applications.identifiers import require_identifier
from fam_os.applications.payloads import freeze_payload
from fam_os.memory import (
    DocumentCorrectionRequest,
    DocumentDeletionRequest,
    DocumentExpirationRequest,
)
from fam_os.adaptation import LiveAdaptationControlRequest
from fam_os.fabric import PeerManagementRequest, RemoteContextSendRequest
from fam_os.schemas import decode_document, encode_document
from fam_os.shell.contracts import (
    ShellAskCommand,
    ShellCancelCommand,
    ShellDecisionCommand,
    ShellSessionSnapshot,
    ShellSnapshotQuery,
    ShellVerifiedAskCommand,
)
from fam_os.shell.memory_contracts import ShellMemoryQuery, ShellMemoryResponse
from fam_os.shell.adaptation_contracts import (
    ShellAdaptationQuery,
    ShellAdaptationResponse,
)
from fam_os.shell.peer_contracts import (
    ShellPeerProbeRequest, ShellPeerQuery, ShellPeerResponse,
)
from fam_os.shell.engineering_authority_contracts import (
    ShellEngineeringActivationRequest,
    ShellEngineeringAuthorityResponse,
    ShellEngineeringContextRequest,
    ShellEngineeringGrantQuery,
    ShellEngineeringRevocationRequest,
)
from fam_os.shell.integration_environment_contracts import (
    ShellIntegrationEnvironmentControlRequest,
    ShellIntegrationEnvironmentQuery,
    ShellIntegrationEnvironmentResponse,
    ShellIntegrationEnvironmentStartRequest,
)
from fam_os.shell.engineering_secret_contracts import (
    ShellEngineeringSecretMutation, ShellEngineeringSecretQuery,
    ShellEngineeringSecretResponse,
)
from fam_os.shell.engineering_candidate_contracts import (
    ShellEngineeringCandidateEditRequest,
    ShellEngineeringCandidateVerificationRequest,
    ShellEngineeringCandidateReverificationRequest,
    ShellEngineeringChangesetApplyRequest,
    ShellEngineeringChangesetPreviewRequest,
    ShellEngineeringIncidentAdvanceRequest,
    ShellEngineeringPublicationRequest,
)
from fam_os.shell.engineering_loop_contracts import (
    ShellEngineeringLoopMutation,
    ShellEngineeringLoopQuery,
    ShellEngineeringLoopResponse,
    ShellEngineeringLoopStartRequest,
)


SHELL_TRANSPORT_VERSION = "fam.shell.local/v1alpha1"
MAX_SHELL_FRAME_BYTES = 8_388_608


class ShellWireKind(StrEnum):
    ASK = "ask"
    VERIFIED_ASK = "verified_ask"
    SNAPSHOT_QUERY = "snapshot_query"
    DECIDE = "decide"
    CANCEL = "cancel"
    MEMORY_QUERY = "memory_query"
    MEMORY_CORRECT = "memory_correct"
    MEMORY_EXPIRE = "memory_expire"
    MEMORY_DELETE = "memory_delete"
    ADAPTATION_QUERY = "adaptation_query"
    ADAPTATION_CONTROL = "adaptation_control"
    PEER_QUERY = "peer_query"
    PEER_PROBE = "peer_probe"
    PEER_CONTROL = "peer_control"
    PEER_CONTEXT = "peer_context"
    ENGINEERING_CONTEXT = "engineering_context"
    ENGINEERING_ACTIVATE = "engineering_activate"
    ENGINEERING_QUERY = "engineering_query"
    ENGINEERING_REVOKE = "engineering_revoke"
    INTEGRATION_ENVIRONMENT_START = "integration_environment_start"
    INTEGRATION_ENVIRONMENT_QUERY = "integration_environment_query"
    INTEGRATION_ENVIRONMENT_CONTROL = "integration_environment_control"
    ENGINEERING_SECRET_QUERY = "engineering_secret_query"
    ENGINEERING_SECRET_MUTATION = "engineering_secret_mutation"
    ENGINEERING_LOOP_START = "engineering_loop_start"
    ENGINEERING_LOOP_QUERY = "engineering_loop_query"
    ENGINEERING_LOOP_MUTATION = "engineering_loop_mutation"
    ENGINEERING_CANDIDATE_EDIT = "engineering_candidate_edit"
    ENGINEERING_CANDIDATE_VERIFY = "engineering_candidate_verify"
    ENGINEERING_CANDIDATE_REVERIFY = "engineering_candidate_reverify"
    ENGINEERING_CHANGESET_PREVIEW = "engineering_changeset_preview"
    ENGINEERING_CHANGESET_APPLY = "engineering_changeset_apply"
    ENGINEERING_PUBLICATION = "engineering_publication"
    ENGINEERING_INCIDENT_ADVANCE = "engineering_incident_advance"
    SNAPSHOT = "snapshot"
    MEMORY_RESPONSE = "memory_response"
    ADAPTATION_RESPONSE = "adaptation_response"
    PEER_RESPONSE = "peer_response"
    ENGINEERING_RESPONSE = "engineering_response"
    INTEGRATION_ENVIRONMENT_RESPONSE = "integration_environment_response"
    ENGINEERING_SECRET_RESPONSE = "engineering_secret_response"
    ENGINEERING_LOOP_RESPONSE = "engineering_loop_response"
    ERROR = "error"


REQUEST_TYPES = {
    ShellWireKind.ASK: ShellAskCommand,
    ShellWireKind.VERIFIED_ASK: ShellVerifiedAskCommand,
    ShellWireKind.SNAPSHOT_QUERY: ShellSnapshotQuery,
    ShellWireKind.DECIDE: ShellDecisionCommand,
    ShellWireKind.CANCEL: ShellCancelCommand,
    ShellWireKind.MEMORY_QUERY: ShellMemoryQuery,
    ShellWireKind.MEMORY_CORRECT: DocumentCorrectionRequest,
    ShellWireKind.MEMORY_EXPIRE: DocumentExpirationRequest,
    ShellWireKind.MEMORY_DELETE: DocumentDeletionRequest,
    ShellWireKind.ADAPTATION_QUERY: ShellAdaptationQuery,
    ShellWireKind.ADAPTATION_CONTROL: LiveAdaptationControlRequest,
    ShellWireKind.PEER_QUERY: ShellPeerQuery,
    ShellWireKind.PEER_PROBE: ShellPeerProbeRequest,
    ShellWireKind.PEER_CONTROL: PeerManagementRequest,
    ShellWireKind.PEER_CONTEXT: RemoteContextSendRequest,
    ShellWireKind.ENGINEERING_CONTEXT: ShellEngineeringContextRequest,
    ShellWireKind.ENGINEERING_ACTIVATE: ShellEngineeringActivationRequest,
    ShellWireKind.ENGINEERING_QUERY: ShellEngineeringGrantQuery,
    ShellWireKind.ENGINEERING_REVOKE: ShellEngineeringRevocationRequest,
    ShellWireKind.INTEGRATION_ENVIRONMENT_START: ShellIntegrationEnvironmentStartRequest,
    ShellWireKind.INTEGRATION_ENVIRONMENT_QUERY: ShellIntegrationEnvironmentQuery,
    ShellWireKind.INTEGRATION_ENVIRONMENT_CONTROL: ShellIntegrationEnvironmentControlRequest,
    ShellWireKind.ENGINEERING_SECRET_QUERY: ShellEngineeringSecretQuery,
    ShellWireKind.ENGINEERING_SECRET_MUTATION: ShellEngineeringSecretMutation,
    ShellWireKind.ENGINEERING_LOOP_START: ShellEngineeringLoopStartRequest,
    ShellWireKind.ENGINEERING_LOOP_QUERY: ShellEngineeringLoopQuery,
    ShellWireKind.ENGINEERING_LOOP_MUTATION: ShellEngineeringLoopMutation,
    ShellWireKind.ENGINEERING_CANDIDATE_EDIT: ShellEngineeringCandidateEditRequest,
    ShellWireKind.ENGINEERING_CANDIDATE_VERIFY: ShellEngineeringCandidateVerificationRequest,
    ShellWireKind.ENGINEERING_CANDIDATE_REVERIFY: ShellEngineeringCandidateReverificationRequest,
    ShellWireKind.ENGINEERING_CHANGESET_PREVIEW: ShellEngineeringChangesetPreviewRequest,
    ShellWireKind.ENGINEERING_CHANGESET_APPLY: ShellEngineeringChangesetApplyRequest,
    ShellWireKind.ENGINEERING_PUBLICATION: ShellEngineeringPublicationRequest,
    ShellWireKind.ENGINEERING_INCIDENT_ADVANCE: ShellEngineeringIncidentAdvanceRequest,
}
RESPONSE_KINDS = {
    ShellWireKind.SNAPSHOT, ShellWireKind.MEMORY_RESPONSE,
    ShellWireKind.ADAPTATION_RESPONSE, ShellWireKind.PEER_RESPONSE,
    ShellWireKind.ENGINEERING_RESPONSE,
    ShellWireKind.INTEGRATION_ENVIRONMENT_RESPONSE,
    ShellWireKind.ENGINEERING_SECRET_RESPONSE, ShellWireKind.ERROR,
    ShellWireKind.ENGINEERING_LOOP_RESPONSE,
}


@dataclass(frozen=True, slots=True)
class ShellWireMessage:
    message_id: str
    kind: ShellWireKind
    payload: Mapping[str, object]
    correlation_id: str | None = None
    contract_version: str = SHELL_TRANSPORT_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "message_id", require_identifier(self.message_id, "message_id"))
        if not isinstance(self.kind, ShellWireKind):
            raise ValueError("shell wire kind is invalid")
        if self.contract_version != SHELL_TRANSPORT_VERSION:
            raise ValueError("unsupported shell transport version")
        object.__setattr__(self, "payload", freeze_payload(self.payload))
        if self.correlation_id is not None:
            object.__setattr__(
                self, "correlation_id",
                require_identifier(self.correlation_id, "correlation_id"),
            )
        if (self.kind in RESPONSE_KINDS) != (self.correlation_id is not None):
            raise ValueError("shell response correlation is invalid")


def request_message(message_id: str, kind: ShellWireKind, value) -> ShellWireMessage:
    expected = REQUEST_TYPES.get(kind)
    if expected is None or not isinstance(value, expected):
        raise ValueError("shell request payload type is invalid")
    return ShellWireMessage(message_id, kind, encode_document(value))


def snapshot_message(
    message_id: str, correlation_id: str, value: ShellSessionSnapshot,
) -> ShellWireMessage:
    return ShellWireMessage(
        message_id, ShellWireKind.SNAPSHOT, encode_document(value), correlation_id
    )


def memory_response_message(
    message_id: str, correlation_id: str, value: ShellMemoryResponse,
) -> ShellWireMessage:
    return ShellWireMessage(
        message_id, ShellWireKind.MEMORY_RESPONSE,
        encode_document(value), correlation_id,
    )


def adaptation_response_message(
    message_id: str, correlation_id: str, value: ShellAdaptationResponse,
) -> ShellWireMessage:
    return ShellWireMessage(
        message_id, ShellWireKind.ADAPTATION_RESPONSE,
        encode_document(value), correlation_id,
    )


def peer_response_message(
    message_id: str, correlation_id: str, value: ShellPeerResponse,
) -> ShellWireMessage:
    return ShellWireMessage(
        message_id, ShellWireKind.PEER_RESPONSE, encode_document(value), correlation_id,
    )


def engineering_response_message(
    message_id: str, correlation_id: str, value: ShellEngineeringAuthorityResponse,
) -> ShellWireMessage:
    return ShellWireMessage(
        message_id, ShellWireKind.ENGINEERING_RESPONSE,
        encode_document(value), correlation_id,
    )


def integration_environment_response_message(
    message_id: str, correlation_id: str,
    value: ShellIntegrationEnvironmentResponse,
) -> ShellWireMessage:
    return ShellWireMessage(
        message_id, ShellWireKind.INTEGRATION_ENVIRONMENT_RESPONSE,
        encode_document(value), correlation_id,
    )


def engineering_secret_response_message(message_id, correlation_id, value):
    return ShellWireMessage(
        message_id, ShellWireKind.ENGINEERING_SECRET_RESPONSE,
        encode_document(value), correlation_id,
    )


def engineering_loop_response_message(message_id, correlation_id, value):
    return ShellWireMessage(
        message_id, ShellWireKind.ENGINEERING_LOOP_RESPONSE,
        encode_document(value), correlation_id,
    )


def error_message(message_id: str, correlation_id: str, code: str) -> ShellWireMessage:
    return ShellWireMessage(
        message_id, ShellWireKind.ERROR,
        {"code": require_identifier(code, "error code")}, correlation_id,
    )


def decode_request(message: ShellWireMessage):
    expected = REQUEST_TYPES.get(message.kind)
    if expected is None:
        raise ValueError("message is not a shell request")
    value = decode_document(_thaw(message.payload))
    if not isinstance(value, expected):
        raise ValueError("shell request schema does not match message kind")
    return value


def decode_snapshot(message: ShellWireMessage) -> ShellSessionSnapshot:
    if message.kind is not ShellWireKind.SNAPSHOT:
        raise ValueError("message is not a shell snapshot")
    value = decode_document(_thaw(message.payload))
    if not isinstance(value, ShellSessionSnapshot):
        raise ValueError("shell response schema is invalid")
    return value


def decode_memory_response(message: ShellWireMessage) -> ShellMemoryResponse:
    if message.kind is not ShellWireKind.MEMORY_RESPONSE:
        raise ValueError("message is not a Shell memory response")
    value = decode_document(_thaw(message.payload))
    if not isinstance(value, ShellMemoryResponse):
        raise ValueError("Shell memory response schema is invalid")
    return value


def decode_adaptation_response(message: ShellWireMessage) -> ShellAdaptationResponse:
    if message.kind is not ShellWireKind.ADAPTATION_RESPONSE:
        raise ValueError("message is not a Shell adaptation response")
    value = decode_document(_thaw(message.payload))
    if not isinstance(value, ShellAdaptationResponse):
        raise ValueError("Shell adaptation response schema is invalid")
    return value


def decode_peer_response(message: ShellWireMessage) -> ShellPeerResponse:
    if message.kind is not ShellWireKind.PEER_RESPONSE:
        raise ValueError("message is not a Shell peer response")
    value = decode_document(_thaw(message.payload))
    if not isinstance(value, ShellPeerResponse):
        raise ValueError("Shell peer response schema is invalid")
    return value


def decode_engineering_response(
    message: ShellWireMessage,
) -> ShellEngineeringAuthorityResponse:
    if message.kind is not ShellWireKind.ENGINEERING_RESPONSE:
        raise ValueError("message is not a Shell engineering response")
    value = decode_document(_thaw(message.payload))
    if not isinstance(value, ShellEngineeringAuthorityResponse):
        raise ValueError("Shell engineering response schema is invalid")
    return value


def decode_integration_environment_response(
    message: ShellWireMessage,
) -> ShellIntegrationEnvironmentResponse:
    if message.kind is not ShellWireKind.INTEGRATION_ENVIRONMENT_RESPONSE:
        raise ValueError("message is not a Shell integration environment response")
    value = decode_document(_thaw(message.payload))
    if not isinstance(value, ShellIntegrationEnvironmentResponse):
        raise ValueError("Shell integration environment response schema is invalid")
    return value


def decode_engineering_secret_response(message):
    if message.kind is not ShellWireKind.ENGINEERING_SECRET_RESPONSE:
        raise ValueError("message is not a Shell engineering secret response")
    value = decode_document(_thaw(message.payload))
    if not isinstance(value, ShellEngineeringSecretResponse):
        raise ValueError("Shell engineering secret response schema is invalid")
    return value


def decode_engineering_loop_response(message):
    if message.kind is not ShellWireKind.ENGINEERING_LOOP_RESPONSE:
        raise ValueError("message is not a Shell engineering loop response")
    value = decode_document(_thaw(message.payload))
    if not isinstance(value, ShellEngineeringLoopResponse):
        raise ValueError("Shell engineering loop response schema is invalid")
    return value


def encode_frame(message: ShellWireMessage, maximum=MAX_SHELL_FRAME_BYTES) -> bytes:
    payload = json.dumps(
        message_document(message), sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")
    if not payload or len(payload) > maximum:
        raise ValueError("shell frame exceeds limit")
    return struct.pack("!I", len(payload)) + payload


def send_frame(stream, message, maximum=MAX_SHELL_FRAME_BYTES) -> None:
    stream.sendall(encode_frame(message, maximum))


def receive_frame(stream, maximum=MAX_SHELL_FRAME_BYTES) -> ShellWireMessage:
    header = _read_exact(stream, 4)
    size = struct.unpack("!I", header)[0]
    if size <= 0 or size > maximum:
        raise ValueError("shell frame size is invalid")
    try:
        document = json.loads(_read_exact(stream, size).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("shell frame is not strict UTF-8 JSON") from error
    return message_from_document(document)


def message_document(message: ShellWireMessage) -> dict[str, object]:
    return {
        "contract_version": message.contract_version,
        "message_id": message.message_id,
        "kind": message.kind.value,
        "correlation_id": message.correlation_id,
        "payload": _thaw(message.payload),
    }


def message_from_document(document) -> ShellWireMessage:
    fields = {"contract_version", "message_id", "kind", "correlation_id", "payload"}
    if not isinstance(document, dict) or set(document) != fields:
        raise ValueError("shell message fields must match exactly")
    if not isinstance(document["payload"], dict):
        raise ValueError("shell message payload must be an object")
    try:
        kind = ShellWireKind(document["kind"])
    except (TypeError, ValueError) as error:
        raise ValueError("shell wire kind is invalid") from error
    return ShellWireMessage(
        document["message_id"], kind, document["payload"],
        document["correlation_id"], document["contract_version"],
    )


def _read_exact(stream, size):
    chunks = []
    remaining = size
    while remaining:
        chunk = stream.recv(remaining)
        if not chunk:
            raise EOFError("shell transport closed during frame")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _thaw(value):
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value
