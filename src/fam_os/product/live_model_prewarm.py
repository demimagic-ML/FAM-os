"""Resource-admitted prompt-free model prewarming for live adaptation."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from uuid import uuid4

from fam_os.adaptation import ModelPrewarmReceipt, ModelPrewarmSource, ModelPrewarmStatus
from fam_os.core.production.contracts import ModelIntent


class LiveModelPrewarmer:
    def __init__(self, repositories, catalog, runtime, model_loader, capacity) -> None:
        self._repositories = repositories
        self._catalog = catalog
        self._runtime = runtime
        self._loader = model_loader
        self._capacity = capacity

    def execute(self, snapshot) -> None:
        residency = self._residency()
        if residency is None:
            return
        selected = self._candidate(snapshot, set(residency))
        if selected is None:
            return
        model, source = selected
        receipt = self._prewarm(snapshot, model, source, set(residency))
        self._repositories.live_adaptation.add_receipt(receipt)

    def _candidate(self, snapshot, resident):
        intent = ModelIntent(snapshot.workflow_id.removeprefix("intent:"))
        entries = self._catalog.for_intent(intent)
        by_ref = {item.model_ref: item for item in entries}
        choices = []
        if snapshot.transition_model_ref in by_ref:
            choices.append((by_ref[snapshot.transition_model_ref], ModelPrewarmSource.TRANSITION))
        if snapshot.prewarm_escalation:
            strong = sorted(
                (item for item in entries if item.tier == "escalation"),
                key=lambda item: (-item.estimated_resident_bytes, item.model_ref),
            )
            choices.extend((item, ModelPrewarmSource.ESCALATION) for item in strong)
        choices.extend(
            (by_ref[model_ref], ModelPrewarmSource.FREQUENCY)
            for model_ref in snapshot.frequency_model_refs if model_ref in by_ref
        )
        return next(
            (choice for choice in choices if choice[0].model_ref not in resident),
            choices[0] if choices else None,
        )

    def _prewarm(self, snapshot, model, source, resident):
        started_at = datetime.now(timezone.utc)
        started = time.perf_counter()
        if model.model_ref in resident:
            return _receipt(
                snapshot, model, source, ModelPrewarmStatus.REJECTED,
                started_at, 0, True, True, started, ("residency.already_loaded",),
            )
        capacity = self._capacity()
        blockers = []
        if not capacity.speculative_prefetch_allowed:
            blockers.append("policy.speculative_prefetch_blocked")
        if not capacity.background_adaptation_allowed:
            blockers.append("policy.background_adaptation_blocked")
        if not capacity.allows_tier(model.tier):
            blockers.append("policy.expert_tier_blocked")
        if blockers:
            reasons = tuple(dict.fromkeys(tuple(blockers) + capacity.reason_codes))
            return _receipt(
                snapshot, model, source, ModelPrewarmStatus.REJECTED,
                started_at, 0, False, False, started, reasons,
            )
        usable = capacity.schedulable_host_bytes + capacity.schedulable_vram_bytes
        if model.estimated_resident_bytes > usable:
            reasons = tuple(dict.fromkeys(
                ("capacity.operating_system_reserve",) + capacity.reason_codes
            ))
            return _receipt(
                snapshot, model, source, ModelPrewarmStatus.REJECTED,
                started_at, 0, False, False, started, reasons,
            )
        return self._load(snapshot, model, source, capacity, started_at, started)

    def _load(self, snapshot, model, source, capacity, started_at, started):
        status = ModelPrewarmStatus.COMPLETED
        reasons = tuple(dict.fromkeys(
            ("prediction.supported", "capacity.within_all_bounds", "eviction.none")
            + capacity.reason_codes
        ))
        try:
            if self._loader is not None:
                self._loader.ensure_model(model.model_ref)
            self._runtime.prewarm(model.model_ref, "10m")
            loaded_after = model.model_ref in set(self._residency() or ())
            if not loaded_after:
                raise RuntimeError("prewarm completed without residency evidence")
        except Exception:
            loaded_after = model.model_ref in set(self._residency() or ())
            status = ModelPrewarmStatus.COMPLETED if loaded_after else ModelPrewarmStatus.FAILED
            reasons = (
                "runtime.resident_after_reported_failure"
                if loaded_after else "runtime.prewarm_failed",
                "eviction.none",
            ) + capacity.reason_codes
            reasons = tuple(dict.fromkeys(reasons))
        return _receipt(
            snapshot, model, source, status, started_at,
            model.estimated_resident_bytes, False, loaded_after, started, reasons,
        )

    def _residency(self) -> tuple[str, ...] | None:
        try:
            return tuple(item.model_ref for item in self._runtime.loaded_models())
        except Exception:
            return None


def _receipt(
    snapshot, model, source, status, started_at, reserved_bytes,
    loaded_before, loaded_after, started, reasons,
) -> ModelPrewarmReceipt:
    return ModelPrewarmReceipt(
        f"prewarm-{uuid4()}", snapshot.snapshot_id, model.model_ref, source, status,
        started_at, datetime.now(timezone.utc), reserved_bytes,
        loaded_before, loaded_after, max(0.0, (time.perf_counter() - started) * 1000),
        reasons,
    )
