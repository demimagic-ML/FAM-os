"""Build exact promoted lineage and invoke signed disabled packaging."""

from __future__ import annotations

import hashlib
import platform
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

from fam_os.expert_factory import (
    FactorySpecialistPackageReceipt,
    build_specialist_release_lineage,
)
from fam_os.product.composition.core_storage import CoreRepositorySet
from fam_os.product.factory_specialist_packaging import FactorySpecialistPackager


class ProductFactoryReleases:
    def __init__(
        self, *, repositories: CoreRepositorySet,
        packager: FactorySpecialistPackager, model_directory: Path,
        conversion_workspace_root: Path,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._repositories = repositories
        self._packager = packager
        self._model_directory = model_directory
        self._conversion_root = conversion_workspace_root
        self._now = now or (lambda: datetime.now(UTC))

    def package(
        self, *, release_id: str, conversion_id: str, package_id: str,
        package_version: str, expert_id: str,
        declared_capabilities: tuple[str, ...],
        required_verifier_ids: tuple[str, ...], tokenizer_path: Path,
        chat_template_path: Path, confirmed: bool,
    ) -> FactorySpecialistPackageReceipt:
        if not confirmed:
            raise PermissionError("specialist packaging requires confirmation")
        receipt = self._repositories.factory_conversions.receipt(conversion_id)
        if receipt is None or receipt.status.value != "completed":
            raise PermissionError("completed specialist conversion is unavailable")
        approval = self._repositories.factory_conversions.approval(
            receipt.approval_id,
        )
        if approval is None:
            raise RuntimeError("specialist conversion approval is unavailable")
        decision = self._repositories.factory_evaluations.decision(
            approval.evaluation_id,
        )
        if decision is None or not decision.promotable or (
            decision.decision_sha256 != approval.comparison_decision_sha256
        ):
            raise PermissionError("specialist comparison is not promotable")
        evaluation = self._repositories.factory_evaluations.approval(
            decision.approval_id,
        )
        report = self._repositories.factory_evaluations.report(
            decision.evaluation_id,
        )
        if evaluation is None or report is None:
            raise RuntimeError("specialist evaluation lineage is incomplete")
        terminal = next((
            item for item in self._repositories.training_jobs.terminals()
            if item.receipt_id == evaluation.training_receipt_id
        ), None)
        if terminal is None:
            raise RuntimeError("specialist training receipt is unavailable")
        training = self._repositories.training_approvals.get(terminal.approval_id)
        if training is None:
            raise RuntimeError("specialist training approval is unavailable")
        _model_file(self._model_directory, tokenizer_path, "tokenizer")
        _model_file(self._model_directory, chat_template_path, "chat template")
        if any(value is None for value in (
            receipt.base_gguf_sha256, receipt.adapter_gguf_sha256,
            receipt.modelfile_sha256,
        )):
            raise RuntimeError("completed conversion lacks runtime digests")
        lineage = build_specialist_release_lineage(
            release_id=release_id, package_id=package_id,
            package_version=package_version, expert_id=expert_id,
            training_capability_id=evaluation.capability_id,
            declared_capabilities=declared_capabilities,
            required_verifier_ids=required_verifier_ids,
            conversion_receipt_id=receipt.receipt_id,
            conversion_receipt_sha256=receipt.receipt_sha256,
            conversion_environment_sha256=receipt.environment_sha256,
            comparison_decision_id=decision.decision_id,
            comparison_decision_sha256=decision.decision_sha256,
            training_receipt_id=terminal.receipt_id,
            sealed_dataset_id=evaluation.sealed_dataset_id,
            sealed_dataset_sha256=evaluation.sealed_dataset_sha256,
            base_model_id=training.base_model.repository_id,
            base_model_revision=training.base_model.revision,
            base_model_files_sha256=training.base_model.files_manifest_sha256,
            adapter_sha256=terminal.adapter_sha256,
            base_gguf_sha256=receipt.base_gguf_sha256,
            adapter_gguf_sha256=receipt.adapter_gguf_sha256,
            modelfile_sha256=receipt.modelfile_sha256,
            tokenizer_sha256=_sha(tokenizer_path),
            chat_template_sha256=_sha(chat_template_path),
            merge_policy="runtime_lora_adapter",
            base_output_type=approval.base_output_type,
            adapter_output_type=approval.adapter_output_type,
            runtime_model_ref=approval.runtime_model_ref,
            license_id=training.base_model.license_id,
            estimated_resident_bytes=(
                receipt.base_gguf_bytes + receipt.adapter_gguf_bytes
            ),
            storage_bytes=(
                receipt.base_gguf_bytes + receipt.adapter_gguf_bytes
                + 1024**2
            ),
            max_context_tokens=training.recipe.maximum_sequence_tokens,
            minimum_system_memory_bytes=max(
                report.candidate_peak_ram_bytes,
                receipt.base_gguf_bytes + receipt.adapter_gguf_bytes,
            ),
            minimum_accelerator_memory_bytes=report.candidate_peak_vram_bytes,
            accelerator_optional=True,
            supported_architectures=(platform.machine(),),
            created_at=self._now(),
        )
        packaged = self._packager.package(
            lineage,
            self._conversion_root / conversion_id / "output",
        )
        self._repositories.factory_releases.record_package(
            lineage, packaged.receipt,
        )
        return packaged.receipt


def _model_file(root: Path, path: Path, label: str) -> None:
    root = root.resolve(strict=True)
    candidate = path.resolve(strict=True)
    if (
        not candidate.is_relative_to(root)
        or not candidate.is_file()
        or path.is_symlink()
    ):
        raise PermissionError(f"specialist {label} file is unsafe")


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
