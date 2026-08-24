"""Owner Console facade for bounded persistent engineering authority."""

from __future__ import annotations

import json

from fam_os.core.engineering.break_glass import BreakGlassChallenge, BreakGlassDecision
from fam_os.core.engineering.grants import EngineeringAuthorityGrant, OwnerGrantApproval
from fam_os.product.engineering_authority import PersistentEngineeringAuthorizer
from fam_os.product.owner_engineering_authentication import (
    OwnerEngineeringAuthenticationRegistry,
)
from fam_os.product.storage.engineering_grant_repository import (
    SqliteEngineeringGrantRepository,
)
from fam_os.schemas import encode_document, loads_document


class ProductEngineeringAuthorityApi:
    """Expose only owner ceremonies, never storage reconfirmation primitives."""

    def __init__(
        self,
        owner_id: str,
        repository: SqliteEngineeringGrantRepository,
        authentication: OwnerEngineeringAuthenticationRegistry,
        authorizer: PersistentEngineeringAuthorizer,
    ) -> None:
        self._owner_id = owner_id
        self._repository = repository
        self._authentication = authentication
        self._authorizer = authorizer

    def issue_context(self, document: dict, session_id: str) -> dict:
        _exact_fields(
            document,
            {"owner_id", "purpose", "payload_sha256", "confirmed"},
        )
        if document["confirmed"] is not True:
            raise PermissionError("engineering authorization requires confirmation")
        owner_id = _text(document["owner_id"], "owner_id")
        purpose = _text(document["purpose"], "purpose")
        digest = _text(document["payload_sha256"], "payload_sha256")
        context = self._authentication.issue(
            owner_id, purpose, digest, transport_session_id=session_id,
        )
        return {
            "context_id": context.context_id,
            "owner_id": context.owner_id,
            "purpose": context.purpose,
            "payload_sha256": context.payload_sha256,
            "issued_at": context.issued_at.isoformat(),
            "expires_at": context.expires_at.isoformat(),
        }

    def activate(self, document: dict, session_id: str) -> dict:
        _exact_fields(
            document,
            {"grant", "approval", "challenge", "decision", "confirmed"},
        )
        if document["confirmed"] is not True:
            raise PermissionError("engineering grant activation requires confirmation")
        grant = _contract(document["grant"], EngineeringAuthorityGrant, "grant")
        approval = _contract(document["approval"], OwnerGrantApproval, "approval")
        challenge = _optional_contract(
            document["challenge"], BreakGlassChallenge, "challenge",
        )
        decision = _optional_contract(
            document["decision"], BreakGlassDecision, "decision",
        )
        if grant.owner_id != self._owner_id:
            raise PermissionError("engineering grant owner is invalid")
        context_ids = [approval.authentication_context_id]
        if decision is not None:
            context_ids.append(decision.authentication_context_id)
        if not all(
            self._authentication.belongs_to_session(context_id, session_id)
            for context_id in context_ids
        ):
            raise PermissionError(
                "engineering authorization context does not belong to this session"
            )
        self._authorizer.activate(grant, approval, challenge, decision)
        return self.inspect(grant.grant_id)

    def revoke(self, grant_id: str, document: dict) -> dict:
        _exact_fields(document, {"owner_id", "confirmed"})
        if document["confirmed"] is not True:
            raise PermissionError("engineering grant revocation requires confirmation")
        owner_id = _text(document["owner_id"], "owner_id")
        if owner_id != self._owner_id:
            raise PermissionError("engineering grant owner is invalid")
        self._authorizer.revoke(grant_id, owner_id)
        return self.inspect(grant_id)

    def inspect(self, grant_id: str) -> dict:
        stored = self._repository.get(_text(grant_id, "grant_id"))
        if stored is None:
            raise KeyError("engineering grant is unavailable")
        grant, _approval, reconfirmation_required = stored
        return {
            "grant": encode_document(grant),
            "reconfirmation_required": reconfirmation_required,
            "usable": self._repository.usable(grant_id) is not None,
        }

    def audit(self, grant_id: str) -> dict:
        if self._repository.get(_text(grant_id, "grant_id")) is None:
            raise KeyError("engineering grant is unavailable")
        decisions = self._repository.decisions(grant_id)
        return {
            "grant_id": grant_id,
            "decisions": [encode_document(decision) for decision in decisions],
        }


def _contract(value, expected, name):
    if not isinstance(value, dict):
        raise ValueError(f"engineering {name} must be a schema envelope")
    decoded = loads_document(json.dumps(value, separators=(",", ":")))
    if not isinstance(decoded, expected):
        raise ValueError(f"engineering {name} schema type is invalid")
    return decoded


def _optional_contract(value, expected, name):
    return None if value is None else _contract(value, expected, name)


def _exact_fields(document: dict, expected: set[str]) -> None:
    if set(document) != expected:
        raise ValueError("engineering authority fields must match exactly")


def _text(value, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"engineering {name} must be non-empty text")
    return value
