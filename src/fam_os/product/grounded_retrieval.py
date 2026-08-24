"""Production grounding over packaged identity and approved document indexes."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib import resources

from fam_os.core.production import ModelIntent
from fam_os.core.production.grounding_port import (
    GroundedRetrievalUnavailable,
    GroundingAccessContext,
)
from fam_os.memory import MemoryAccessContext, scope_allows
from fam_os.verification import (
    RetrievalCitationsVerification,
    RetrievedSource,
    VerificationDeclaration,
    contract_for_kind,
    missing_retrieval_terms,
    retrieval_query_obligation,
)


@dataclass(frozen=True, slots=True)
class GroundedRetrievalPolicy:
    purpose_id: str = "assist"
    maximum_sources: int = 8
    candidate_sources: int = 16
    maximum_source_characters: int = 32_768
    minimum_similarity: float = 0.15

    def __post_init__(self) -> None:
        if not self.purpose_id.strip():
            raise ValueError("grounded retrieval purpose must not be empty")
        if not 1 <= self.maximum_sources <= self.candidate_sources <= 32:
            raise ValueError("grounded retrieval source limits are invalid")
        if not 1 <= self.maximum_source_characters <= 262_144:
            raise ValueError("grounded retrieval character limit is invalid")
        if not -1 <= self.minimum_similarity <= 1:
            raise ValueError("grounded retrieval similarity is invalid")


class ProductGroundedRetrieval:
    def __init__(
        self,
        index,
        repository,
        owner_id: str,
        model_loader=None,
        policy: GroundedRetrievalPolicy | None = None,
        clock=None,
    ) -> None:
        if not owner_id.strip():
            raise ValueError("grounded retrieval owner must not be empty")
        self._index = index
        self._repository = repository
        self._owner_id = owner_id
        self._loader = model_loader
        self._policy = policy or GroundedRetrievalPolicy()
        self._clock = clock or (lambda: datetime.now(UTC))

    def declaration_for(
        self,
        request_id: str,
        prompt: str,
        intent: ModelIntent,
        access: GroundingAccessContext,
    ) -> VerificationDeclaration:
        if intent not in {ModelIntent.GROUNDED_QUESTION, ModelIntent.RETRIEVAL}:
            raise ValueError("grounded retrieval received an ineligible intent")
        try:
            query = retrieval_query_obligation(prompt)
        except ValueError as error:
            raise GroundedRetrievalUnavailable(
                "The request has no bounded significant terms for deterministic grounding. "
                "Make the question more specific and try again."
            ) from error
        identity = _identity_source()
        sources = (
            (identity,)
            if "famos" in query.required_terms
            and not missing_retrieval_terms((identity.content,), query)
            else self._document_sources(prompt, access)
        )
        if not sources or missing_retrieval_terms(
            tuple(item.content for item in sources), query,
        ):
            raise GroundedRetrievalUnavailable(
                "No active approved local source covered every significant request term. "
                "Approve a relevant document or folder in FAM Console and try again."
            )
        specification = RetrievalCitationsVerification(sources, query)
        return VerificationDeclaration(
            f"declaration-{request_id}", request_id,
            contract_for_kind(specification.kind), specification,
        )

    def _document_sources(
        self, prompt: str, access: GroundingAccessContext,
    ) -> tuple[RetrievedSource, ...]:
        now = self._clock()
        self._repository.purge_expired(now)
        context = MemoryAccessContext(
            self._owner_id, self._policy.purpose_id,
            application_id=access.application_id,
            workspace_id=access.workspace_id,
            session_id=access.session_id,
        )
        grants = tuple(
            grant for grant in self._repository.grants()
            if now < grant.expires_at and scope_allows(grant.scope, context)
        )
        if not grants:
            return ()
        models = {grant.embedding_model_ref for grant in grants}
        if len(models) != 1:
            raise RuntimeError("one grounded request cannot mix embedding models")
        if self._loader is not None:
            self._loader.ensure_model(next(iter(models)))
        hits = self._index.retrieve(
            prompt, context, self._policy.candidate_sources, now=now,
        )
        return self._bounded_sources(hits, now)

    def _bounded_sources(self, hits, now: datetime) -> tuple[RetrievedSource, ...]:
        selected: list[RetrievedSource] = []
        characters = 0
        for hit in hits:
            if hit.score < self._policy.minimum_similarity:
                continue
            approval = self._repository.approval(hit.document_id)
            if approval is None or approval.expires_at is None or now >= approval.expires_at:
                continue
            source = _indexed_source(hit, approval)
            if characters + len(source.content) > self._policy.maximum_source_characters:
                continue
            selected.append(source)
            characters += len(source.content)
            if len(selected) == self._policy.maximum_sources:
                break
        return tuple(selected)


def _identity_source() -> RetrievedSource:
    content = resources.files("fam_os.product.resources").joinpath(
        "FAM_OS_IDENTITY.md",
    ).read_text(encoding="utf-8")
    digest = _digest(content)
    return RetrievedSource(
        "fam-os-product-identity",
        "package://fam_os/product/FAM_OS_IDENTITY.md",
        content,
        digest,
        f"package-resource-{digest}",
    )


def _indexed_source(hit, approval) -> RetrievedSource:
    content_digest = _digest(hit.content)
    identity = _digest(
        "\x00".join((
            approval.grant_id or "legacy", hit.document_id, hit.chunk_id,
            content_digest, approval.source_sha256,
        ))
    )
    return RetrievedSource(
        f"indexed-{identity[:24]}", hit.source_locator, hit.content,
        content_digest, f"document-index-{identity}",
    )


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
