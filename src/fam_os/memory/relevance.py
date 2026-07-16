"""Deterministic scope, relevance, freshness, and volume gating."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from fam_os.memory.access import MemoryAccessContext, scope_allows
from fam_os.memory.manifest import MemoryScope

MEMORY_RELEVANCE_CONTRACT_VERSION = "fam.memory.relevance/v1alpha1"


@dataclass(frozen=True, slots=True)
class MemoryRetrievalCandidate:
    record_id: str
    scope: MemoryScope
    captured_at: datetime
    relevance_score: float
    estimated_tokens: int

    def __post_init__(self) -> None:
        if self.captured_at.tzinfo is None or not 0 <= self.relevance_score <= 1:
            raise ValueError("memory candidate requires time and normalized score")
        if self.estimated_tokens <= 0:
            raise ValueError("memory candidate token estimate must be positive")


@dataclass(frozen=True, slots=True)
class MemoryRejection:
    record_id: str
    reason_code: str


@dataclass(frozen=True, slots=True)
class MemoryRelevanceDecision:
    selected_record_ids: tuple[str, ...]
    selected_tokens: int
    rejections: tuple[MemoryRejection, ...]
    contract_version: str = MEMORY_RELEVANCE_CONTRACT_VERSION


@dataclass(frozen=True, slots=True)
class MemoryRelevancePolicy:
    minimum_score: float
    maximum_age: timedelta
    maximum_context_tokens: int

    def __post_init__(self) -> None:
        if not 0 <= self.minimum_score <= 1 or self.maximum_age <= timedelta(0):
            raise ValueError("memory relevance score and age bounds are invalid")
        if self.maximum_context_tokens <= 0:
            raise ValueError("memory context budget must be positive")

    def decide(self, candidates, context: MemoryAccessContext, now: datetime):
        if now.tzinfo is None:
            raise ValueError("memory relevance time must be timezone-aware")
        eligible, rejected = [], []
        for candidate in candidates:
            reason = self._rejection(candidate, context, now)
            if reason is None:
                eligible.append(candidate)
            else:
                rejected.append(MemoryRejection(candidate.record_id, reason))
        eligible.sort(key=lambda item: (-item.relevance_score, item.record_id))
        selected, tokens = [], 0
        for candidate in eligible:
            if tokens + candidate.estimated_tokens > self.maximum_context_tokens:
                rejected.append(MemoryRejection(candidate.record_id, "memory.context-budget"))
                continue
            selected.append(candidate.record_id)
            tokens += candidate.estimated_tokens
        return MemoryRelevanceDecision(tuple(selected), tokens, tuple(rejected))

    def _rejection(self, candidate, context, now):
        if not scope_allows(candidate.scope, context):
            return "memory.scope-denied"
        if now - candidate.captured_at > self.maximum_age:
            return "memory.stale"
        if candidate.relevance_score < self.minimum_score:
            return "memory.low-relevance"
        return None
