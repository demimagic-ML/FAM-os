"""Run a disabled specialist through its exact scheduler and verifier canary."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Callable, Protocol

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from fam_os.core.ports.inference import (
    InferenceMessage,
    InferenceRequest,
    InferenceRuntime,
    MessageRole,
)
from fam_os.core.production.contracts import ModelIntent, RuntimeModelEntry
from fam_os.core.production.model_catalog import RuntimeModelCatalog
from fam_os.core.production.model_selection import (
    HostCapacity,
    ResourceAwareModelSelector,
)
from fam_os.expert_factory import (
    FactoryActivationDecision,
    FactoryCanaryApproval,
    FactoryCanaryStatus,
    FactorySpecialistReleaseLineage,
    build_canary_approval,
    build_canary_report,
    decide_canary_activation,
)
from fam_os.product.composition.core_storage import CoreRepositorySet
from fam_os.product.factory_runtime_bundle import (
    extract_factory_runtime_bundle,
    factory_package_artifact,
)


class CanaryVerifier(Protocol):
    def verify(
        self, *, verifier_id: str, case_id: str, candidate: str,
        bundle_id: str, test_source: str,
    ) -> bool: ...


class CanaryModelInstaller(Protocol):
    def create(self, model_ref: str, modelfile: Path) -> str: ...
    def remove(self, model_ref: str) -> None: ...


class ProductFactoryCanaryApprovals:
    def __init__(
        self, repositories: CoreRepositorySet,
        suite_path: Path | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._repositories = repositories
        self._suite_path = suite_path
        self._now = now or (lambda: datetime.now(UTC))

    def issue(
        self, *, request_id: str, package_receipt_id: str, suite_path: Path,
        verifier_id: str, maximum_output_tokens: int,
        maximum_wall_seconds: int, maximum_ram_bytes: int,
        maximum_vram_bytes: int, one_use_canary_id: str,
        lifetime_seconds: int, confirmed: bool,
    ) -> FactoryCanaryApproval:
        if not confirmed:
            raise PermissionError("factory canary requires confirmation")
        if not 60 <= lifetime_seconds <= 24 * 60 * 60:
            raise ValueError("factory canary lifetime is invalid")
        if self._suite_path is not None and (
            suite_path.resolve(strict=True)
            != self._suite_path.resolve(strict=True)
        ):
            raise PermissionError("factory canary suite is not the configured suite")
        package = self._repositories.factory_releases.package_receipt(
            package_receipt_id,
        )
        if package is None or not package.installed_disabled:
            raise PermissionError("signed disabled specialist is unavailable")
        lineage = self._repositories.factory_releases.lineage(package.release_id)
        if lineage is None:
            raise RuntimeError("specialist release lineage is unavailable")
        cases = _suite(suite_path)
        if verifier_id not in lineage.required_verifier_ids:
            raise PermissionError("canary verifier is not release-bound")
        now = self._now()
        approval = build_canary_approval(
            approval_id=f"canary-approval-{request_id}",
            release_id=lineage.release_id,
            package_receipt_sha256=package.receipt_sha256,
            package_id=lineage.package_id,
            package_version=lineage.package_version,
            expert_id=lineage.expert_id,
            runtime_model_ref=lineage.runtime_model_ref,
            capability_id=lineage.training_capability_id,
            verifier_id=verifier_id, suite_sha256=_sha(suite_path),
            case_count=len(cases), maximum_output_tokens=maximum_output_tokens,
            maximum_wall_seconds=maximum_wall_seconds,
            maximum_ram_bytes=maximum_ram_bytes,
            maximum_vram_bytes=maximum_vram_bytes,
            one_use_canary_id=one_use_canary_id, issued_at=now,
            expires_at=now + timedelta(seconds=lifetime_seconds),
        )
        if not self._repositories.factory_releases.add_canary_approval(approval):
            existing = self._repositories.factory_releases.canary_approval(
                approval.approval_id,
            )
            if existing is None or existing != approval:
                raise RuntimeError("factory canary approval identity was reused")
            return existing
        return approval


class FactorySpecialistCanaryRunner:
    def __init__(
        self, *, repositories: CoreRepositorySet, artifact_root: Path,
        suite_path: Path, workspace_root: Path,
        installer: CanaryModelInstaller, runtime: InferenceRuntime,
        verifier: CanaryVerifier, signer_key_id: str,
        signing_key: Ed25519PrivateKey,
        now: Callable[[], datetime] | None = None,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._repositories = repositories
        self._artifact_root = artifact_root
        self._suite_path = suite_path
        self._workspace_root = workspace_root
        self._installer = installer
        self._runtime = runtime
        self._verifier = verifier
        self._signer_key_id = signer_key_id
        self._signing_key = signing_key
        self._now = now or (lambda: datetime.now(UTC))
        self._monotonic = monotonic

    def run(
        self, *, approval_id: str, confirmed: bool,
    ) -> FactoryActivationDecision:
        if not confirmed:
            raise PermissionError("factory canary execution requires confirmation")
        approval = self._repositories.factory_releases.canary_approval(approval_id)
        if approval is None:
            raise KeyError("factory canary approval is unavailable")
        existing = self._repositories.factory_releases.activation_decision(
            approval.one_use_canary_id,
        )
        if existing is not None:
            return existing
        package = self._repositories.factory_releases.package_receipt_by_sha(
            approval.package_receipt_sha256,
        )
        lineage = self._repositories.factory_releases.lineage(approval.release_id)
        if package is None or lineage is None:
            raise RuntimeError("factory canary package lineage is unavailable")
        _require_approval_lineage(approval, lineage, package.receipt_sha256)
        cases = _suite(self._suite_path)
        if _sha(self._suite_path) != approval.suite_sha256 or (
            len(cases) != approval.case_count
        ):
            raise PermissionError("factory canary suite changed after approval")
        artifact = factory_package_artifact(
            self._artifact_root, package.artifact_locator,
        )
        self._repositories.factory_releases.claim_canary(
            approval.approval_id, approval.one_use_canary_id,
            approval.revision, self._now(),
        )
        started = self._now()
        started_monotonic = self._monotonic()
        manifest_sha = hashlib.sha256(b"").hexdigest()
        passed = failures = peak_ram = peak_vram = 0
        selected, excluded = _scheduler_scope(approval, lineage)
        status = FactoryCanaryStatus.FAILED
        reason = "canary.worker_failed"
        created = False
        self._workspace_root.mkdir(parents=True, mode=0o700, exist_ok=True)
        workspace = Path(tempfile.mkdtemp(
            prefix=f"{approval.one_use_canary_id}-",
            dir=self._workspace_root,
        ))
        try:
            runtime_directory = workspace / "runtime"
            extract_factory_runtime_bundle(artifact, runtime_directory)
            manifest_sha = self._installer.create(
                approval.runtime_model_ref, runtime_directory / "Modelfile",
            )
            created = True
            for index, case in enumerate(cases):
                if self._monotonic() - started_monotonic > (
                    approval.maximum_wall_seconds
                ):
                    reason = "canary.wall_time_exceeded"
                    break
                response = self._runtime.chat(InferenceRequest(
                    model_ref=approval.runtime_model_ref,
                    messages=(InferenceMessage(
                        MessageRole.USER, case["prompt"],
                    ),),
                    context_tokens=min(lineage.max_context_tokens, 8192),
                    max_output_tokens=approval.maximum_output_tokens,
                    keep_alive="5m", temperature=0, seed=42,
                ))
                verified = self._verifier.verify(
                    verifier_id=approval.verifier_id,
                    case_id=case["case_id"], candidate=response.content,
                    bundle_id=case["bundle_id"],
                    test_source=case["test_source"],
                )
                if not verified:
                    failures += 1
                else:
                    passed += 1
                loaded = next((
                    item for item in self._runtime.loaded_models()
                    if item.model_ref == approval.runtime_model_ref
                ), None)
                if loaded is not None:
                    peak_ram = max(peak_ram, loaded.resident_bytes or 0)
                    peak_vram = max(peak_vram, loaded.accelerator_bytes or 0)
            else:
                status = FactoryCanaryStatus.COMPLETED
                reason = "canary.completed"
        except Exception:
            status = FactoryCanaryStatus.FAILED
            reason = "canary.worker_failed"
        finally:
            shutil.rmtree(workspace)
        finished = self._now()
        report = build_canary_report(
            report_id=f"canary-report-{approval.one_use_canary_id}",
            approval_id=approval.approval_id,
            canary_id=approval.one_use_canary_id,
            package_receipt_sha256=approval.package_receipt_sha256,
            suite_sha256=approval.suite_sha256,
            runtime_manifest_sha256=manifest_sha, status=status,
            reason_code=reason, case_count=approval.case_count,
            passed_case_count=passed, verifier_failure_count=failures,
            scheduler_selected_declared_capability=selected,
            scheduler_excluded_unrelated_capabilities=excluded,
            outputs_discarded=True, peak_ram_bytes=peak_ram,
            peak_vram_bytes=peak_vram, started_at=started,
            finished_at=finished,
        )
        decision = decide_canary_activation(
            decision_id=f"activation-{approval.one_use_canary_id}",
            approval=approval, report=report,
            signer_key_id=self._signer_key_id,
            signing_key=self._signing_key, decided_at=finished,
        )
        if created and not decision.activate:
            self._installer.remove(approval.runtime_model_ref)
        self._repositories.factory_releases.complete_canary(report, decision)
        return decision


def _suite(path: Path) -> tuple[dict[str, str], ...]:
    if not path.is_file() or path.is_symlink() or path.stat().st_size > 1024**2:
        raise ValueError("factory canary suite is unavailable or too large")
    cases = []
    for line in path.read_text("utf-8").splitlines():
        value = json.loads(line)
        expected = {"case_id", "prompt", "bundle_id", "test_source"}
        if not isinstance(value, dict) or set(value) != expected:
            raise ValueError("factory canary case is invalid")
        if any(
            not isinstance(value[name], str) or not value[name].strip()
            for name in expected
        ) or len(value["prompt"]) > 32_000 or len(value["test_source"]) > 131_072:
            raise ValueError("factory canary case content is invalid")
        cases.append({name: value[name] for name in expected})
    if not cases or len({item["case_id"] for item in cases}) != len(cases):
        raise ValueError("factory canary cases must be nonempty and unique")
    return tuple(cases)


def _scheduler_scope(
    approval: FactoryCanaryApproval,
    lineage: FactorySpecialistReleaseLineage,
) -> tuple[bool, bool]:
    intent = _intent(approval.capability_id)
    if intent is None:
        return False, False
    entry = RuntimeModelEntry(
        lineage.runtime_model_ref, "specialist", (intent,),
        lineage.estimated_resident_bytes, lineage.max_context_tokens,
        approval.package_receipt_sha256, lineage.required_verifier_ids,
    )
    selector = ResourceAwareModelSelector(RuntimeModelCatalog((entry,)))
    capacity = HostCapacity(
        approval.maximum_ram_bytes, approval.maximum_vram_bytes,
    )
    try:
        selection = selector.select("factory-canary", intent, capacity)
    except LookupError:
        return False, False
    excluded = True
    for unrelated in ModelIntent:
        if unrelated is intent:
            continue
        try:
            selector.select(f"factory-canary-{unrelated.value}", unrelated, capacity)
        except LookupError:
            continue
        excluded = False
        break
    return selection.model_ref == lineage.runtime_model_ref, excluded


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


def _require_approval_lineage(
    approval: FactoryCanaryApproval,
    lineage: FactorySpecialistReleaseLineage,
    package_sha256: str,
) -> None:
    if (
        approval.release_id != lineage.release_id
        or approval.package_id != lineage.package_id
        or approval.package_version != lineage.package_version
        or approval.expert_id != lineage.expert_id
        or approval.runtime_model_ref != lineage.runtime_model_ref
        or approval.capability_id != lineage.training_capability_id
        or approval.verifier_id not in lineage.required_verifier_ids
        or approval.package_receipt_sha256 != package_sha256
    ):
        raise PermissionError("factory canary approval lineage changed")


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
