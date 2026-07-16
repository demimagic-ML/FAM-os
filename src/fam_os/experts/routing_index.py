"""Atomic routing-embedding index that returns evidence, not policy decisions."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock

from fam_os.experts.registry_contracts import ExpertPackageCoordinate
from fam_os.experts.routing_metadata import (
    ExpertRoutingEmbedding,
    ExpertRoutingMatch,
    RoutingEmbeddingQuery,
)
from fam_os.experts.ports import ExpertRoutingEmbeddingSource


@dataclass(slots=True)
class ExpertRoutingEmbeddingIndex:
    _values: dict[tuple[ExpertPackageCoordinate, str], ExpertRoutingEmbedding] = field(
        default_factory=dict
    )
    _lock: Lock = field(default_factory=Lock)

    def refresh(self, values: tuple[ExpertRoutingEmbedding, ...]) -> bool:
        updated = _validated(values)
        with self._lock:
            changed = tuple(
                key for key in set(updated) & set(self._values)
                if updated[key] != self._values[key]
            )
            if changed:
                raise ValueError("routing embedding identity changed without a new ID")
            if updated == self._values:
                return False
            self._values = updated
            return True

    def rank(
        self,
        query: RoutingEmbeddingQuery,
        eligible_coordinates: frozenset[ExpertPackageCoordinate] | None = None,
        limit: int = 10,
    ) -> tuple[ExpertRoutingMatch, ...]:
        if not 1 <= limit <= 100:
            raise ValueError("routing match limit must be between 1 and 100")
        with self._lock:
            values = tuple(self._values.values())
        candidates = tuple(
            value for value in values
            if _eligible(value, query, eligible_coordinates)
        )
        matches = tuple(_match(value, query) for value in candidates)
        return tuple(sorted(matches, key=_match_key)[:limit])

    def refresh_from(self, source: ExpertRoutingEmbeddingSource) -> bool:
        return self.refresh(source.load())

    def snapshot(self) -> tuple[ExpertRoutingEmbedding, ...]:
        with self._lock:
            return tuple(sorted(self._values.values(), key=_embedding_key))


def _validated(values):
    result = {}
    dimensions = {}
    for value in values:
        if not isinstance(value, ExpertRoutingEmbedding):
            raise ValueError("routing index requires ExpertRoutingEmbedding values")
        key = (value.coordinate, value.embedding_id)
        if key in result:
            raise ValueError("duplicate routing embedding identity")
        prior = dimensions.setdefault(value.embedding_space_id, len(value.vector))
        if prior != len(value.vector):
            raise ValueError("one embedding space must have one vector dimension")
        result[key] = value
    return result


def _eligible(value, query, eligible):
    return (
        value.embedding_space_id == query.embedding_space_id
        and len(value.vector) == len(query.vector)
        and (eligible is None or value.coordinate in eligible)
        and set(query.required_capabilities).issubset(value.capabilities)
    )


def _match(value, query):
    similarity = sum(left * right for left, right in zip(value.vector, query.vector))
    similarity = max(-1.0, min(1.0, similarity))
    return ExpertRoutingMatch(
        value.coordinate, value.expert_id, value.embedding_id,
        similarity, value.benchmark_run_ids,
    )


def _match_key(value):
    return (-value.cosine_similarity, value.coordinate, value.embedding_id)


def _embedding_key(value):
    return value.coordinate, value.embedding_id
