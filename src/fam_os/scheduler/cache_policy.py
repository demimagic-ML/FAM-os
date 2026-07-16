"""Pure tier-separated deterministic cache retention policy."""

from __future__ import annotations

from fam_os.scheduler.cache_contracts import (
    CacheEntryState,
    CacheEvictionDecision,
    CachePolicyDecision,
    CachePolicyRequest,
    CacheTier,
    CacheTierReclaim,
)


class DeterministicCacheRetentionPolicy:
    def decide(self, decision_id: str, request: CachePolicyRequest) -> CachePolicyDecision:
        selected: list[CacheEvictionDecision] = []
        reclaims: list[CacheTierReclaim] = []
        rank = 1
        for pressure in request.pressures:
            candidates = self._candidates(request, pressure.tier)
            freed = 0
            for entry in candidates:
                if freed >= pressure.required_free_bytes:
                    break
                selected.append(CacheEvictionDecision(
                    entry.tier, entry.artifact_id, rank, entry.observed_bytes,
                    "warm.unprotected.least_recent_low_hit_low_reload_cost",
                ))
                rank += 1
                freed += entry.observed_bytes
            reclaims.append(CacheTierReclaim(
                pressure.tier, pressure.required_free_bytes, freed,
                freed >= pressure.required_free_bytes,
            ))
        return CachePolicyDecision(
            decision_id, request.request_id, tuple(selected), tuple(reclaims),
            all(item.satisfied for item in reclaims),
        )

    @staticmethod
    def _candidates(request: CachePolicyRequest, tier: CacheTier):
        protected = set(request.protected_artifact_ids)
        candidates = (
            item for item in request.snapshot.entries
            if item.tier is tier and item.state is CacheEntryState.WARM
            and item.evictable and item.artifact_id not in protected
        )
        return tuple(sorted(candidates, key=lambda item: (
            item.last_accessed_at, item.hit_count, item.reload_cost_ms, item.artifact_id,
        )))
