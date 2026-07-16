"""Auditable evidence contract for the three-tier retrieval pipeline."""

from dataclasses import dataclass

RETRIEVAL_EVIDENCE_CONTRACT_VERSION = "fam.expert.retrieval-evidence/v1alpha1"


@dataclass(frozen=True, slots=True)
class RetrievalTierEvidence:
    evidence_id: str
    embedding_expert_id: str
    embedding_model_ref: str
    embedding_artifact_sha256: str
    embedding_dimension: int
    reranking_expert_id: str
    ranked_source_ids: tuple[str, ...]
    synthesis_expert_id: str
    synthesis_model_ref: str
    synthesis_artifact_sha256: str
    cited_source_ids: tuple[str, ...]
    verified_claim_ids: tuple[str, ...]
    answer: str
    released: bool
    contract_version: str = RETRIEVAL_EVIDENCE_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.embedding_dimension <= 0 or not self.ranked_source_ids:
            raise ValueError("retrieval evidence requires embeddings and ranking")
        if not self.cited_source_ids or not self.verified_claim_ids:
            raise ValueError("retrieval evidence requires verified citations")
        if not self.released or not self.answer.strip():
            raise ValueError("retrieval evidence must prove a released answer")
        for digest in (self.embedding_artifact_sha256, self.synthesis_artifact_sha256):
            if len(digest) != 64 or any(value not in "0123456789abcdef" for value in digest):
                raise ValueError("artifact digests must be lowercase SHA-256")
