"""Natural-language publication checkpoint and separate owner ceremony."""

from fam_os.core.engineering import (
    EngineeringAuthority, git_publication_proposal_digest,
)
from fam_os.schemas import encode_document


class NaturalEngineeringPublicationCoordinator:
    def __init__(
        self, loop, *, remote_name=None, credential_ref=None,
        activate_grant, attach_rollback,
    ) -> None:
        self._loop = loop
        self._remote_name = remote_name
        self._credential_ref = credential_ref
        self._activate_grant = activate_grant
        self._attach_rollback = attach_rollback

    def attach(self, response, proposal, *, create, changeset_id=None) -> None:
        if (
            EngineeringAuthority.PUBLISH
            not in proposal.separately_confirmed_authorities
        ):
            return
        owner_id, task_id = (
            proposal.grant.owner_id, proposal.definition.task.task_id,
        )
        try:
            publication = self._loop.publication_for_task(owner_id, task_id)
            if publication is None and create:
                publication = self._prepare(response, proposal, changeset_id)
            if publication is None:
                return
            response["publication_proposal"] = self.view(publication)
            status = self._loop.publication_status(
                owner_id, publication.proposal_id,
            )
            response["publication_status"] = status
            if status == "prepared":
                response["outcome"] = "publication_approval_required"
        except (KeyError, PermissionError, RuntimeError, ValueError) as error:
            response["publication_unavailable_reason"] = str(error)

    def approve(
        self, owner_id, proposal, publication_proposal_id,
        transport_session_id, *, confirmed,
    ):
        if not isinstance(confirmed, bool):
            raise PermissionError("natural engineering publication decision is invalid")
        publication = self._loop.publication_for_task(
            owner_id, proposal.definition.task.task_id,
        )
        if publication is None or publication.proposal_id != publication_proposal_id:
            raise PermissionError("natural engineering publication proposal changed")
        if not confirmed:
            self._loop.decline_publication_proposal(
                owner_id, publication.proposal_id,
            )
            response = self._loop.inspect(owner_id, publication.task_id)
            response.update({
                "outcome": "publication_declined",
                "publication_proposal": self.view(publication),
            })
            self._attach_rollback(response, owner_id, publication.task_id)
            return response
        if not self._loop.publication_grant_matches(owner_id, publication.grant):
            self._activate_grant(
                owner_id, publication.grant, transport_session_id,
                purpose="engineering-publication-grant",
            )
        receipt = self._loop.approve_publication_proposal(
            owner_id, publication.proposal_id,
        )
        response = self._loop.inspect(owner_id, publication.task_id)
        response.update({
            "outcome": "publication_completed",
            "publication_proposal": self.view(publication),
            "publication_receipt": encode_document(receipt),
        })
        return response

    def view(self, publication) -> dict:
        return {
            "document": encode_document(publication),
            "approval_sha256": git_publication_proposal_digest(publication),
            "status": self._loop.publication_status(
                publication.grant.owner_id, publication.proposal_id,
            ),
        }

    def _prepare(self, response, proposal, changeset_id):
        if not self._remote_name or not self._credential_ref or changeset_id is None:
            raise RuntimeError(
                "natural Git publication remote and credential reference are not configured"
            )
        title = _commit_message(proposal.definition.task.intent)[5:]
        evidence = ", ".join(response.get("test_receipt_ids", ()))
        return self._loop.prepare_publication(
            proposal.grant.owner_id, proposal.definition.task.task_id,
            changeset_id, remote_name=self._remote_name,
            credential_ref=self._credential_ref, title=title,
            body=(
                "FAM_OS verified this exact changeset before and after apply. "
                f"Verification evidence: {evidence}"
            ),
        )


def _commit_message(intent: str) -> str:
    normalized = " ".join(intent.split())
    return "FAM: " + normalized[:200]
