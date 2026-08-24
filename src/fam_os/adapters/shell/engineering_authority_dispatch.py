"""Map typed owner Shell requests onto the product authority facade."""

from datetime import datetime

from fam_os.schemas import decode_document, encode_document
from fam_os.shell.engineering_authority_contracts import (
    ShellEngineeringActivationRequest,
    ShellEngineeringAuthorityOperation,
    ShellEngineeringAuthorityResponse,
    ShellEngineeringContextRequest,
    ShellEngineeringGrantQuery,
    ShellEngineeringRevocationRequest,
)


class EngineeringAuthorityUnavailable(RuntimeError):
    """The installed product has no engineering authority facade."""


def dispatch_engineering_authority(authority, command):
    if authority is None:
        raise EngineeringAuthorityUnavailable
    if isinstance(command, ShellEngineeringContextRequest):
        result = authority.issue_context({
            "owner_id": command.owner_id,
            "purpose": command.purpose,
            "payload_sha256": command.payload_sha256,
            "confirmed": command.confirmed,
        }, command.authority_session_id)
        return ShellEngineeringAuthorityResponse(
            command.request_id, ShellEngineeringAuthorityOperation.ISSUE_CONTEXT,
            context_id=result["context_id"],
            expires_at=datetime.fromisoformat(result["expires_at"]),
        )
    if isinstance(command, ShellEngineeringActivationRequest):
        result = authority.activate({
            "grant": encode_document(command.grant),
            "approval": encode_document(command.approval),
            "challenge": None if command.challenge is None else encode_document(command.challenge),
            "decision": None if command.decision is None else encode_document(command.decision),
            "confirmed": command.confirmed,
        }, command.authority_session_id)
        return _grant_response(command.request_id, ShellEngineeringAuthorityOperation.ACTIVATE, result)
    if isinstance(command, ShellEngineeringGrantQuery):
        if command.operation is ShellEngineeringAuthorityOperation.AUDIT:
            result = authority.audit(command.grant_id)
            return ShellEngineeringAuthorityResponse(
                command.request_id, command.operation,
                decisions=tuple(_decode(item) for item in result["decisions"]),
            )
        return _grant_response(
            command.request_id, command.operation, authority.inspect(command.grant_id),
        )
    if isinstance(command, ShellEngineeringRevocationRequest):
        result = authority.revoke(command.grant_id, {
            "owner_id": command.owner_id, "confirmed": command.confirmed,
        })
        return _grant_response(command.request_id, ShellEngineeringAuthorityOperation.REVOKE, result)
    raise ValueError("unsupported Shell engineering authority request")


def _grant_response(request_id, operation, result):
    return ShellEngineeringAuthorityResponse(
        request_id, operation, grant=_decode(result["grant"]),
        reconfirmation_required=result["reconfirmation_required"],
        usable=result["usable"],
    )


def _decode(document):
    return decode_document(document)
