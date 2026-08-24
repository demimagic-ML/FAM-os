"""Promotion-gated one-use runtime conversion approval service."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Callable, Protocol

from fam_os.adapters.training.conversion_environment import (
    LlamaCppConversionEnvironmentProbe,
)
from fam_os.expert_factory import (
    ConversionOutputType,
    FactoryConversionApproval,
    FactoryConversionEnvironment,
    FactoryConversionReceipt,
    build_conversion_approval,
)
from fam_os.product.composition.core_storage import CoreRepositorySet


class FactoryConversionRunner(Protocol):
    def run(
        self, *, approval_id: str, confirmed: bool,
    ) -> FactoryConversionReceipt: ...


class ProductFactoryConversions:
    def __init__(
        self,
        repositories: CoreRepositorySet,
        environment_probe: LlamaCppConversionEnvironmentProbe,
        backend: FactoryConversionRunner | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._repositories = repositories
        self._probe = environment_probe
        self._backend = backend
        self._now = now or (lambda: datetime.now(UTC))

    def probe_environment(self) -> FactoryConversionEnvironment:
        environment = self._probe.probe()
        self._repositories.factory_conversions.add_environment(environment)
        return environment

    def issue(
        self, *, request_id: str, evaluation_id: str, environment_sha256: str,
        base_output_type: ConversionOutputType,
        adapter_output_type: ConversionOutputType, runtime_model_ref: str,
        maximum_output_bytes: int, maximum_wall_seconds: int,
        maximum_ram_bytes: int, maximum_cpu_cores: int,
        one_use_conversion_id: str,
        lifetime_seconds: int, confirmed: bool,
    ) -> FactoryConversionApproval:
        if not confirmed:
            raise PermissionError("conversion approval requires confirmation")
        if not 60 <= lifetime_seconds <= 24 * 60 * 60:
            raise ValueError("conversion approval lifetime must be 60 seconds to 24 hours")
        decision = self._repositories.factory_evaluations.decision(evaluation_id)
        if decision is None:
            raise KeyError("signed comparison decision is unavailable")
        if not decision.promotable:
            raise PermissionError(
                "conversion denied by signed comparison: "
                + ",".join(decision.reason_codes),
            )
        evaluation = self._repositories.factory_evaluations.approval(
            decision.approval_id,
        )
        if evaluation is None or evaluation.one_use_evaluation_id != evaluation_id:
            raise RuntimeError("evaluation approval lineage is unavailable")
        if self._repositories.factory_conversions.environment(environment_sha256) is None:
            raise PermissionError("pinned conversion environment is unavailable")
        now = self._now()
        approval = build_conversion_approval(
            approval_id=f"conversion-approval-{request_id}",
            evaluation_id=evaluation_id,
            comparison_decision_id=decision.decision_id,
            comparison_decision_sha256=decision.decision_sha256,
            adapter_sha256=evaluation.adapter_sha256,
            base_model_sha256=evaluation.incumbent_artifact_sha256,
            environment_sha256=environment_sha256,
            base_output_type=base_output_type,
            adapter_output_type=adapter_output_type,
            runtime_model_ref=runtime_model_ref,
            maximum_output_bytes=maximum_output_bytes,
            maximum_wall_seconds=maximum_wall_seconds,
            maximum_ram_bytes=maximum_ram_bytes,
            maximum_cpu_cores=maximum_cpu_cores,
            one_use_conversion_id=one_use_conversion_id, issued_at=now,
            expires_at=now + timedelta(seconds=lifetime_seconds),
        )
        if not self._repositories.factory_conversions.add_approval(approval):
            existing = self._repositories.factory_conversions.approval(
                approval.approval_id,
            )
            if existing != approval:
                raise RuntimeError("conversion approval request identity was reused")
            if existing is None:
                raise RuntimeError("conversion approval disappeared")
            return existing
        return approval

    def run(
        self, *, approval_id: str, confirmed: bool,
    ) -> FactoryConversionReceipt:
        if self._backend is None:
            raise RuntimeError("real conversion backend is not configured")
        return self._backend.run(
            approval_id=approval_id, confirmed=confirmed,
        )
