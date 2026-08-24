"""Separate owner ceremony for exact natural integration resources."""

from fam_os.core.engineering import EngineeringAuthority
from fam_os.core.engineering.grant_policy import engineering_grant_digest
from fam_os.schemas import encode_document


class NaturalEngineeringIntegrationAuthorityCoordinator:
    def __init__(self, grant_reader, activate_grant) -> None:
        self._grant_reader = grant_reader
        self._activate_grant = activate_grant

    def allowed_separate(self, proposal) -> set[EngineeringAuthority]:
        allowed = {EngineeringAuthority.PUBLISH}
        if self.usable(proposal):
            allowed.update(
                authority for authority
                in proposal.integration_resource_grant.authorities
                if authority is not EngineeringAuthority.EXECUTE
            )
        return allowed

    def approve(
        self, owner_id, proposal, proposal_status, transport_session_id, *,
        confirmed,
    ) -> None:
        if confirmed is not True:
            raise PermissionError(
                "natural integration resource activation requires confirmation"
            )
        grant = proposal.integration_resource_grant
        if grant is None:
            raise PermissionError(
                "natural integration resources are not exactly specified"
            )
        if proposal.grant.owner_id != owner_id:
            raise PermissionError("natural engineering proposal owner is invalid")
        if proposal_status not in {"proposed", "interrupted", "activated"}:
            raise PermissionError(
                "natural integration resource proposal is not pending"
            )
        if not self.usable(proposal):
            self._activate_grant(
                owner_id, grant, transport_session_id,
                purpose="engineering-integration-resource-grant",
            )
        if not self.usable(proposal):
            raise RuntimeError(
                "natural integration resource grant was not persisted as usable"
            )

    def attach(self, value: dict, proposal) -> None:
        grant = proposal.integration_resource_grant
        value["integration_resource_grant"] = (
            None if grant is None else {
                "document": encode_document(grant),
                "approval_sha256": engineering_grant_digest(grant),
                "status": (
                    "approved" if self.usable(proposal)
                    else "approval_required"
                ),
            }
        )

    def usable(self, proposal) -> bool:
        grant = proposal.integration_resource_grant
        if grant is None or self._grant_reader is None:
            return False
        return self._grant_reader.usable(grant.grant_id) == grant
