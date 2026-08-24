"""Resource-aware primary and escalation model selection."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from fam_os.core.production.contracts import (
    ModelIntent,
    RuntimeModelEntry,
    RuntimeModelSelection,
)
from fam_os.core.production.model_catalog import RuntimeModelCatalog
from fam_os.core.production.adaptation_port import LiveAdaptationPort


_GIBIBYTE = 1024**3
_TIER_ORDER = {
    "micro": 0,
    "embedding": 0,
    "economical": 1,
    "specialist": 2,
    "escalation": 3,
}


@dataclass(frozen=True, slots=True)
class HostCapacity:
    available_host_bytes: int
    available_vram_bytes: int = 0
    reserved_host_bytes: int = 2 * _GIBIBYTE
    reserved_vram_bytes: int = 0
    host_allocation_ceiling_bytes: int | None = None
    reclaimable_host_bytes: int = 0
    reclaimable_vram_bytes: int = 0
    maximum_expert_tier: str = "escalation"
    speculative_prefetch_allowed: bool = True
    background_adaptation_allowed: bool = True
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        byte_values = (
            self.available_host_bytes,
            self.available_vram_bytes,
            self.reserved_host_bytes,
            self.reserved_vram_bytes,
            self.reclaimable_host_bytes,
            self.reclaimable_vram_bytes,
        )
        if min(byte_values) < 0:
            raise ValueError("host capacity cannot be negative")
        if (
            self.host_allocation_ceiling_bytes is not None
            and self.host_allocation_ceiling_bytes < 0
        ):
            raise ValueError("host allocation ceiling cannot be negative")
        if self.maximum_expert_tier not in {
            "micro", "economical", "specialist", "escalation",
        }:
            raise ValueError("maximum expert tier is invalid")
        if len(set(self.reason_codes)) != len(self.reason_codes):
            raise ValueError("capacity reason codes must be unique")

    @property
    def schedulable_host_bytes(self) -> int:
        available = max(0, self.available_host_bytes - self.reserved_host_bytes)
        if self.host_allocation_ceiling_bytes is not None:
            available = min(available, self.host_allocation_ceiling_bytes)
        return available

    @property
    def schedulable_vram_bytes(self) -> int:
        return max(0, self.available_vram_bytes - self.reserved_vram_bytes)

    def allows_tier(self, tier: str) -> bool:
        return _TIER_ORDER[tier] <= _TIER_ORDER[self.maximum_expert_tier]


class ResourceAwareModelSelector:
    def __init__(
        self,
        catalog: RuntimeModelCatalog,
        adaptation: LiveAdaptationPort | None = None,
    ) -> None:
        self._catalog = catalog
        self._adaptation = adaptation

    def select(
        self,
        request_id: str,
        intent: ModelIntent,
        capacity: HostCapacity,
        *,
        escalation: bool = False,
        resident_model_refs: tuple[str, ...] = (),
        excluded_model_refs: tuple[str, ...] = (),
        required_verifier_id: str | None = None,
    ) -> RuntimeModelSelection:
        excluded = set(excluded_model_refs)
        intent_candidates = tuple(
            entry for entry in self._catalog.for_intent(intent)
            if entry.model_ref not in excluded
        )
        candidates = tuple(
            entry for entry in intent_candidates if (
                required_verifier_id is None
                or required_verifier_id in entry.verifier_ids
            )
        )
        if required_verifier_id is not None and not candidates:
            raise LookupError(
                "no local model declares required verifier compatibility: "
                + required_verifier_id
            )
        resident = set(resident_model_refs)
        fitting = tuple(
            entry for entry in candidates
            if capacity.allows_tier(entry.tier)
            and (entry.model_ref in resident or _fits(entry, capacity))
        )
        if not fitting:
            raise LookupError("no local model fits the live resource budget")
        preferred = (
            () if self._adaptation is None
            else self._adaptation.preferred_model_refs(intent)
        )
        preference = {model_ref: index for index, model_ref in enumerate(preferred)}
        ordered = sorted(
            fitting,
            key=lambda entry: _selection_rank(
                entry, escalation, resident, preference,
            ),
        )
        selected = ordered[0]
        reasons = ["capability.intent_match", "resources.host_vram_fit"]
        if required_verifier_id is not None:
            reasons.append("verification.declared_compatibility")
        if (
            selected.model_ref not in resident
            and not _fits_without_reclaim(selected, capacity)
        ):
            reasons.append("resources.reclaimable_warm_fit")
        reasons.append(
            "policy.strong_escalation" if escalation else "policy.economical_first"
        )
        reasons.append(
            "residency.already_loaded"
            if selected.model_ref in resident else "residency.cold_load"
        )
        if selected.model_ref in preference:
            reasons.append("adaptation.verified_frequency_preference")
        reasons.extend(
            reason for reason in capacity.reason_codes if reason not in reasons
        )
        return RuntimeModelSelection(
            str(uuid4()), request_id, intent, selected.model_ref, selected.tier,
            selected.estimated_resident_bytes, capacity.available_host_bytes,
            capacity.available_vram_bytes, tuple(reasons),
        )


def _fits(entry: RuntimeModelEntry, capacity: HostCapacity) -> bool:
    # Ollama may split weights between VRAM and host RAM. Only explicitly
    # schedulable bytes count; OS, foreground, GPU, and cgroup reserves do not.
    usable = (
        capacity.schedulable_host_bytes
        + capacity.schedulable_vram_bytes
        + capacity.reclaimable_host_bytes
        + capacity.reclaimable_vram_bytes
    )
    return entry.estimated_resident_bytes <= usable


def _fits_without_reclaim(
    entry: RuntimeModelEntry, capacity: HostCapacity,
) -> bool:
    usable = capacity.schedulable_host_bytes + capacity.schedulable_vram_bytes
    return entry.estimated_resident_bytes <= usable


def _rank(entry: RuntimeModelEntry, escalation: bool) -> tuple[int, int, str]:
    if escalation:
        tier = {"escalation": 0, "specialist": 1, "economical": 2, "embedding": 3}
        return tier[entry.tier], -entry.estimated_resident_bytes, entry.model_ref
    tier = {"specialist": 0, "economical": 1, "escalation": 2, "embedding": 3}
    return tier[entry.tier], entry.estimated_resident_bytes, entry.model_ref


def _selection_rank(entry, escalation, resident, preference):
    tier, size, model_ref = _rank(entry, escalation)
    learned = preference.get(entry.model_ref, len(preference))
    residency = entry.model_ref not in resident
    if escalation:
        return tier, residency, learned, size, model_ref
    return tier, residency, learned, size, model_ref
