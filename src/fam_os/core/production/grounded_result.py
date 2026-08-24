"""Post-verification presentation of exact retrieval citations."""

from __future__ import annotations

from dataclasses import replace

from fam_os.core.contracts import ResultCitation, ResultStatus, TaskResult
from fam_os.verification import RetrievalCitationsVerification
from fam_os.verification.retrieval_candidate import parse_retrieval_candidate


class GroundedResultPresenter:
    def __init__(self, verification_repository) -> None:
        self._verifications = verification_repository

    def present(self, result: TaskResult) -> TaskResult:
        declaration = self._verifications.declaration_for_request(result.request_id)
        if declaration is None or not isinstance(
            declaration.specification, RetrievalCitationsVerification,
        ):
            return result
        if declaration.specification.query is None:
            # Historical v1alpha1 declarations remain readable, but the hardened
            # verifier will never accept a newly executed unbound declaration.
            return result
        if result.status is not ResultStatus.VERIFIED or not result.verified:
            return result
        if result.content is None:
            raise RuntimeError("verified retrieval result has no candidate content")
        parsed = parse_retrieval_candidate(result.content, declaration.specification)
        citations = tuple(
            ResultCitation(
                citation_id=item.citation.citation_id,
                claim_id=item.claim_id,
                claim_text=item.text,
                source_id=item.source.source_id,
                source_locator=item.source.locator,
                source_content_sha256=item.source.content_sha256,
                provenance_id=item.source.provenance_id,
                start_character=item.citation.start_character,
                end_character=item.citation.end_character,
                quoted_text=item.quote,
                quoted_text_sha256=item.citation.quoted_text_sha256,
            )
            for item in parsed.claims
        )
        return replace(result, content=parsed.answer, citations=citations)
