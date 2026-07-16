"""Semantic candidate evidence constrained to enabled expert packages."""

from __future__ import annotations

from dataclasses import dataclass

from fam_os.experts.routing_index import ExpertRoutingEmbeddingIndex
from fam_os.experts.routing_metadata import (
    ExpertRoutingMatch,
    RoutingEmbeddingQuery,
)
from fam_os.registry.lifecycle_contracts import ExpertPackageInstallationState
from fam_os.routing.contracts import RoutingRequest
from fam_os.routing.ports import RoutingTextEmbedder


@dataclass(slots=True)
class SemanticExpertCandidateFinder:
    index: ExpertRoutingEmbeddingIndex
    embedder: RoutingTextEmbedder
    embedding_space_id: str

    def __post_init__(self) -> None:
        if not self.embedding_space_id.strip():
            raise ValueError("embedding_space_id must not be empty")

    def find(
        self,
        request: RoutingRequest,
        installation_state: ExpertPackageInstallationState,
        limit: int = 10,
    ) -> tuple[ExpertRoutingMatch, ...]:
        vector = self.embedder.embed(self.embedding_space_id, request.prompt)
        query = RoutingEmbeddingQuery(
            self.embedding_space_id,
            vector,
            request.required_capabilities,
        )
        enabled = frozenset(
            package.coordinate for package in installation_state.packages if package.enabled
        )
        return self.index.rank(query, enabled, limit)
