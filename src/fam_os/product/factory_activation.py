"""Apply a signed successful canary to live routing as a separate operation."""

from __future__ import annotations

from fam_os.core.production.contracts import ModelIntent, RuntimeModelEntry
from fam_os.core.production.model_catalog import (
    RuntimeModelCatalog,
    RuntimeModelProvenance,
)
from fam_os.experts.registry_contracts import ExpertPackageCoordinate
from fam_os.product.composition.core_storage import CoreRepositorySet
from fam_os.registry.lifecycle import ExpertPackageLifecycle
from fam_os.registry.lifecycle_contracts import ExpertPackageInstallationState


class ProductFactoryActivation:
    def __init__(
        self, repositories: CoreRepositorySet,
        lifecycle: ExpertPackageLifecycle,
        catalog: RuntimeModelCatalog,
    ) -> None:
        self._repositories = repositories
        self._lifecycle = lifecycle
        self._catalog = catalog

    def activate(
        self, *, canary_id: str, confirmed: bool,
    ) -> ExpertPackageInstallationState:
        if not confirmed:
            raise PermissionError("specialist activation requires confirmation")
        decision = self._repositories.factory_releases.activation_decision(
            canary_id,
        )
        if decision is None:
            raise KeyError("signed specialist activation decision is unavailable")
        if not decision.activate:
            raise PermissionError(
                "specialist activation was denied: "
                + ",".join(decision.reason_codes),
            )
        approval = self._repositories.factory_releases.canary_approval(
            decision.approval_id,
        )
        package = self._repositories.factory_releases.package_receipt_by_sha(
            decision.package_receipt_sha256,
        )
        if approval is None or package is None:
            raise RuntimeError("specialist activation lineage is unavailable")
        lineage = self._repositories.factory_releases.lineage(package.release_id)
        if lineage is None or (
            approval.release_id != lineage.release_id
            or approval.expert_id != lineage.expert_id
            or approval.runtime_model_ref != lineage.runtime_model_ref
        ):
            raise PermissionError("specialist activation lineage changed")
        intent = _intent(lineage.training_capability_id)
        if intent is None:
            raise PermissionError("specialist capability is not routable")
        coordinate = ExpertPackageCoordinate(
            lineage.package_id, lineage.package_version,
        )
        entry = RuntimeModelEntry(
            lineage.runtime_model_ref, "specialist", (intent,),
            lineage.estimated_resident_bytes, lineage.max_context_tokens,
            package.artifact_sha256, lineage.required_verifier_ids,
        )
        provenance = RuntimeModelProvenance(
            lineage.runtime_model_ref, lineage.expert_id,
            f"{lineage.package_id}@{lineage.package_version}",
            f"ollama.local/v1:{lineage.runtime_model_ref}",
            (intent,), entry.verifier_ids,
        )
        self._catalog.validate_runtime_install(entry, provenance)
        state = self._lifecycle.activate(coordinate)
        self._repositories.expert_enablement.synchronize(provenance, entry)
        self._catalog.install_runtime_model(entry, provenance)
        return state


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
