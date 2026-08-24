"""Restart-safe rollback and retirement for generated specialist packages."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, Protocol

from fam_os.core.production.contracts import ModelIntent, RuntimeModelEntry
from fam_os.core.production.model_catalog import (
    RuntimeModelCatalog,
    RuntimeModelProvenance,
)
from fam_os.expert_factory import (
    FactorySpecialistLifecycleAction,
    FactorySpecialistLifecycleReceipt,
    FactorySpecialistLifecycleRequest,
    build_specialist_lifecycle_receipt,
    build_specialist_lifecycle_request,
)
from fam_os.experts.registry_contracts import ExpertPackageCoordinate
from fam_os.product.composition.core_storage import CoreRepositorySet
from fam_os.product.factory_runtime_bundle import (
    extract_factory_runtime_bundle,
    factory_package_artifact,
)
from fam_os.registry.lifecycle import ExpertPackageLifecycle


class SpecialistRuntimeInstaller(Protocol):
    def create(self, model_ref: str, modelfile: Path) -> str: ...
    def remove(self, model_ref: str) -> None: ...


class ProductFactoryLifecycle:
    def __init__(
        self, *, repositories: CoreRepositorySet,
        lifecycle: ExpertPackageLifecycle, catalog: RuntimeModelCatalog,
        installer: SpecialistRuntimeInstaller, artifact_root: Path,
        workspace_root: Path,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._repositories = repositories
        self._lifecycle = lifecycle
        self._catalog = catalog
        self._installer = installer
        self._artifact_root = artifact_root
        self._workspace_root = workspace_root
        self._now = now or (lambda: datetime.now(UTC))

    def manual_rollback(
        self, *, request_id: str, release_id: str,
        target_release_id: str | None, expected_lifecycle_revision: int,
        reason_code: str, confirmed: bool,
    ) -> FactorySpecialistLifecycleReceipt:
        if not confirmed:
            raise PermissionError("manual specialist rollback requires confirmation")
        return self._begin_and_execute(
            request_id=request_id,
            action=FactorySpecialistLifecycleAction.MANUAL_ROLLBACK,
            release_id=release_id, target_release_id=target_release_id,
            expected_lifecycle_revision=expected_lifecycle_revision,
            reason_code=reason_code, regression_evidence_sha256=None,
            remove_artifact=False,
        )

    def forced_regression_rollback(
        self, *, request_id: str, release_id: str,
        target_release_id: str | None, expected_lifecycle_revision: int,
        reason_code: str, regression_evidence_sha256: str,
    ) -> FactorySpecialistLifecycleReceipt:
        return self._begin_and_execute(
            request_id=request_id,
            action=FactorySpecialistLifecycleAction.FORCED_REGRESSION_ROLLBACK,
            release_id=release_id, target_release_id=target_release_id,
            expected_lifecycle_revision=expected_lifecycle_revision,
            reason_code=reason_code,
            regression_evidence_sha256=regression_evidence_sha256,
            remove_artifact=False,
        )

    def retire(
        self, *, request_id: str, release_id: str,
        expected_lifecycle_revision: int, reason_code: str,
        remove_artifact: bool, confirmed: bool,
    ) -> FactorySpecialistLifecycleReceipt:
        if not confirmed:
            raise PermissionError("specialist retirement requires confirmation")
        return self._begin_and_execute(
            request_id=request_id,
            action=FactorySpecialistLifecycleAction.RETIRE,
            release_id=release_id, target_release_id=None,
            expected_lifecycle_revision=expected_lifecycle_revision,
            reason_code=reason_code, regression_evidence_sha256=None,
            remove_artifact=remove_artifact,
        )

    def reconcile(self) -> tuple[FactorySpecialistLifecycleReceipt, ...]:
        return tuple(
            self._execute(request)
            for request in self._repositories.factory_lifecycle.pending()
        )

    def receipts(self) -> tuple[FactorySpecialistLifecycleReceipt, ...]:
        return self._repositories.factory_lifecycle.receipts()

    def observe_production_regression(self, record, decision) -> None:
        run = decision.run_record
        if (
            run is None
            or run.status.value != "failed"
            or run.effective_trust != "signed"
        ):
            return
        provenances = tuple(
            item for item in self._catalog.provenances()
            if item.model_ref == record.selection.model_ref
        )
        if not provenances:
            return
        all_lineages = self._repositories.factory_releases.lineages()
        candidate = next((
            lineage
            for provenance in provenances
            for lineage in all_lineages
            if lineage.expert_id == provenance.expert_id
            and lineage.runtime_model_ref == record.selection.model_ref
            and f"{lineage.package_id}@{lineage.package_version}"
            == provenance.package_ref
        ), None)
        if candidate is None:
            return
        lineages = tuple(
            item for item in all_lineages
            if item.expert_id == candidate.expert_id
        )
        state = self._lifecycle.state_store.load()
        candidate_coordinate = ExpertPackageCoordinate(
            candidate.package_id, candidate.package_version,
        )
        installed = next((
            item for item in state.packages
            if item.coordinate == candidate_coordinate and item.enabled
        ), None)
        if installed is None:
            return
        available = {
            (item.package_id, item.package_version): item for item in lineages
            if item.release_id != candidate.release_id
        }
        targets = tuple(
            (item, available.get((item.coordinate.package_id,
                                  item.coordinate.package_version)))
            for item in state.packages
            if item.expert_id == candidate.expert_id and not item.enabled
        )
        target = next(
            (lineage for _, lineage in sorted(
                targets, key=lambda pair: pair[0].installed_at, reverse=True,
            ) if lineage is not None),
            None,
        )
        evidence = hashlib.sha256(json.dumps({
            "acceptance_id": run.acceptance_id,
            "candidate_id": run.candidate_id,
            "request_id": run.request_id,
            "verification_id": run.verification_id,
            "verified_artifact_sha256": run.verified_artifact_sha256,
        }, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        self.forced_regression_rollback(
            request_id=f"forced-regression-{run.verification_id}",
            release_id=candidate.release_id,
            target_release_id=None if target is None else target.release_id,
            expected_lifecycle_revision=state.revision,
            reason_code="production.verifier_regression",
            regression_evidence_sha256=evidence,
        )

    def _begin_and_execute(self, **values) -> FactorySpecialistLifecycleReceipt:
        existing_request = self._repositories.factory_lifecycle.request(
            values["request_id"],
        )
        if existing_request is not None:
            expected = (
                values["action"], values["release_id"],
                values["target_release_id"],
                values["expected_lifecycle_revision"], values["reason_code"],
                values["regression_evidence_sha256"], values["remove_artifact"],
            )
            observed = (
                existing_request.action, existing_request.release_id,
                existing_request.target_release_id,
                existing_request.expected_lifecycle_revision,
                existing_request.reason_code,
                existing_request.regression_evidence_sha256,
                existing_request.remove_artifact,
            )
            if observed != expected:
                raise RuntimeError("specialist lifecycle request identity was reused")
            return self._execute(existing_request)
        state = self._lifecycle.state_store.load()
        expected = values["expected_lifecycle_revision"]
        if state.revision != expected:
            raise PermissionError("specialist lifecycle revision changed")
        request = build_specialist_lifecycle_request(
            **values, issued_at=self._now(),
        )
        self._validate_request(request, state)
        self._repositories.factory_lifecycle.begin(request)
        return self._execute(request)

    def _validate_request(self, request, state) -> None:
        candidate_lineage, _ = self._release(request.release_id)
        candidate = ExpertPackageCoordinate(
            candidate_lineage.package_id, candidate_lineage.package_version,
        )
        installed = next(
            (item for item in state.packages if item.coordinate == candidate),
            None,
        )
        if installed is None:
            raise KeyError("specialist release is not installed")
        if request.action is not FactorySpecialistLifecycleAction.RETIRE and (
            not installed.enabled
        ):
            raise PermissionError("rollback candidate is not active")
        if request.target_release_id is not None:
            target_lineage, _ = self._release(request.target_release_id)
            if target_lineage.expert_id != candidate_lineage.expert_id:
                raise PermissionError("rollback target belongs to another expert")
            target = ExpertPackageCoordinate(
                target_lineage.package_id, target_lineage.package_version,
            )
            if not any(item.coordinate == target for item in state.packages):
                raise KeyError("rollback target is not installed")

    def _execute(
        self, request: FactorySpecialistLifecycleRequest,
    ) -> FactorySpecialistLifecycleReceipt:
        existing = self._repositories.factory_lifecycle.receipt_for_request(
            request.request_id,
        )
        if existing is not None:
            return existing
        candidate_lineage, candidate_package = self._release(request.release_id)
        candidate_coordinate = ExpertPackageCoordinate(
            candidate_lineage.package_id, candidate_lineage.package_version,
        )
        state = self._lifecycle.state_store.load()
        installed = next(
            (item for item in state.packages if item.coordinate == candidate_coordinate),
            None,
        )
        artifact_removed = installed is None
        active_release_id = None
        self._catalog.remove_runtime_model(candidate_lineage.runtime_model_ref)
        self._repositories.expert_enablement.set_enabled(
            candidate_lineage.expert_id, False,
        )
        self._installer.remove(candidate_lineage.runtime_model_ref)
        if request.action is FactorySpecialistLifecycleAction.RETIRE:
            if installed is not None and installed.enabled:
                state = self._lifecycle.disable(candidate_coordinate)
            if request.remove_artifact and any(
                item.coordinate == candidate_coordinate for item in state.packages
            ):
                state = self._lifecycle.remove(candidate_coordinate)
                artifact_removed = True
        elif request.target_release_id is None:
            if installed is not None and installed.enabled:
                state = self._lifecycle.disable(candidate_coordinate)
        else:
            target_lineage, target_package = self._release(
                request.target_release_id,
            )
            target_coordinate = ExpertPackageCoordinate(
                target_lineage.package_id, target_lineage.package_version,
            )
            target = next(
                (item for item in state.packages if item.coordinate == target_coordinate),
                None,
            )
            if target is None:
                raise KeyError("rollback target is no longer installed")
            if not target.enabled:
                state = self._lifecycle.rollback(target_coordinate)
            self._restore_runtime(target_lineage, target_package)
            entry, provenance = _runtime_model(target_lineage, target_package)
            self._repositories.expert_enablement.synchronize(provenance, entry)
            if not self._repositories.expert_enablement.set_enabled(
                target_lineage.expert_id, True,
            ):
                raise RuntimeError("rollback target enablement is unavailable")
            self._catalog.install_runtime_model(entry, provenance)
            active_release_id = request.target_release_id
        receipt = build_specialist_lifecycle_receipt(
            receipt_id=f"factory-lifecycle-receipt-{request.request_id}",
            request_id=request.request_id,
            request_sha256=request.request_sha256,
            action=request.action, release_id=request.release_id,
            target_release_id=request.target_release_id,
            reason_code=request.reason_code,
            lifecycle_revision=state.revision,
            active_release_id=active_release_id,
            runtime_model_removed=True,
            artifact_removed=artifact_removed,
            audit_retained=True, completed_at=self._now(),
        )
        self._repositories.factory_lifecycle.complete(receipt)
        return receipt

    def _restore_runtime(self, lineage, package) -> None:
        self._workspace_root.mkdir(parents=True, mode=0o700, exist_ok=True)
        workspace = Path(tempfile.mkdtemp(
            prefix="factory-rollback-", dir=self._workspace_root,
        ))
        try:
            runtime = workspace / "runtime"
            extract_factory_runtime_bundle(
                factory_package_artifact(
                    self._artifact_root, package.artifact_locator,
                ),
                runtime,
            )
            manifest_sha256 = self._installer.create(
                lineage.runtime_model_ref, runtime / "Modelfile",
            )
            if len(manifest_sha256) != 64:
                raise RuntimeError("restored specialist manifest is invalid")
        finally:
            shutil.rmtree(workspace)

    def _release(self, release_id: str):
        lineage = self._repositories.factory_releases.lineage(release_id)
        package = next((
            item for item in self._repositories.factory_releases.package_receipts()
            if item.release_id == release_id
        ), None)
        if lineage is None or package is None:
            raise KeyError("specialist release lineage is unavailable")
        return lineage, package


def _runtime_model(lineage, package):
    intent = _intent(lineage.training_capability_id)
    if intent is None:
        raise PermissionError("specialist capability is not routable")
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
    return entry, provenance


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
