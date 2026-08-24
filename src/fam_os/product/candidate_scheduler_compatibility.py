"""Pre-package specialist check against the production model selector."""

from __future__ import annotations

from fam_os.core.production.contracts import ModelIntent, RuntimeModelEntry
from fam_os.core.production.model_catalog import RuntimeModelCatalog
from fam_os.core.production.model_selection import (
    HostCapacity,
    ResourceAwareModelSelector,
)
from fam_os.expert_factory import (
    FactoryEvaluationApproval,
    PairedEvaluationMeasurement,
)


class CandidateSchedulerCompatibilityProbe:
    """Prove exact-capability eligibility before conversion authority exists."""

    def compatible(
        self, *, approval: FactoryEvaluationApproval,
        measurements: tuple[PairedEvaluationMeasurement, ...],
        base_artifact_bytes: int, adapter_bytes: int,
    ) -> bool:
        intent = _intent(approval.capability_id)
        if intent is None:
            return False
        if not measurements or min(base_artifact_bytes, adapter_bytes) < 1:
            return False
        estimated_resident = base_artifact_bytes + adapter_bytes
        entry = RuntimeModelEntry(
            model_ref=f"factory-provisional:{approval.one_use_evaluation_id}",
            tier="specialist", intents=(intent,),
            estimated_resident_bytes=estimated_resident,
            max_context_tokens=8192,
            manifest_sha256=approval.adapter_sha256,
            verifier_ids=(),
        )
        selector = ResourceAwareModelSelector(RuntimeModelCatalog((entry,)))
        capacity = HostCapacity(
            approval.policy.maximum_peak_ram_bytes,
            approval.policy.maximum_peak_vram_bytes,
        )
        try:
            selected = selector.select(
                f"evaluation-{approval.one_use_evaluation_id}", intent, capacity,
            )
        except LookupError:
            return False
        if selected.model_ref != entry.model_ref:
            return False
        for unrelated in ModelIntent:
            if unrelated is intent:
                continue
            try:
                selector.select(
                    f"evaluation-unrelated-{unrelated.value}", unrelated, capacity,
                )
            except LookupError:
                continue
            return False
        return True


def _intent(capability_id: str) -> ModelIntent | None:
    value = capability_id
    for prefix in ("intent.", "intent:"):
        if value.startswith(prefix):
            value = value.removeprefix(prefix)
            break
    try:
        return ModelIntent(value)
    except ValueError:
        return None
