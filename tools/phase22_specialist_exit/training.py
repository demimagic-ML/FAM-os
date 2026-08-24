"""Approve and execute one real promotion checkpoint through product services."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import math
from typing import Any

from fam_os.expert_factory import (
    AdapterTrainingMethod,
    AdapterTrainingRecipe,
    ApprovedBaseModel,
    FactoryTrainingApproval,
    TrainingBackendEnvironment,
    TrainingComputeDtype,
    TrainingResourceBudget,
    TrainingTerminalReceipt,
)
from fam_os.product.composition.factory_training import (
    FactoryTrainingRuntimeSettings,
    compose_factory_training,
)
from fam_os.product.factory_training_approvals import (
    ProductFactoryTrainingApprovals,
)
from tools.phase22_specialist_exit.dataset import PreparedSpecialistDataset
from tools.phase22_specialist_exit.settings import SpecialistExitPaths


GIB = 1024**3


@dataclass(frozen=True, slots=True)
class CompletedSpecialistTraining:
    environment: TrainingBackendEnvironment
    approval: FactoryTrainingApproval
    terminal: TrainingTerminalReceipt
    admissions: tuple[Any, ...]
    jobs: tuple[Any, ...]
    terminals: tuple[TrainingTerminalReceipt, ...]


def run_specialist_training(
    *, paths: SpecialistExitPaths, repositories: Any, blob_store: Any,
    prepared: PreparedSpecialistDataset, now: datetime, run_id: str,
) -> CompletedSpecialistTraining:
    service = compose_factory_training(
        FactoryTrainingRuntimeSettings(
            paths.training_environment, paths.training_manifest,
            paths.model_directory, paths.training_worker,
            paths.output_root / "jobs",
        ),
        repositories, blob_store, paths.output_root.stat().st_uid,
    )
    environment = service.probe_environment()
    training_examples = next(
        item.record_count for item in prepared.dataset.partitions
        if item.partition.value == "train"
    )
    approval = ProductFactoryTrainingApprovals(
        repositories, now=lambda: now,
    ).issue(
        request_id=f"{run_id}-training-approval",
        proposal_id=prepared.proposal.proposal_id,
        sealed_dataset_id=prepared.dataset.dataset_id,
        approved_dataset_license_ids=prepared.dataset.license_ids,
        approved_dataset_sensitivities=prepared.dataset.sensitivities,
        base_model=ApprovedBaseModel(
            "Qwen/Qwen3-1.7B",
            "70d244cc86ccca08cf5af4e1e306ecf908b1ad5e",
            "Qwen/Qwen3-1.7B",
            "70d244cc86ccca08cf5af4e1e306ecf908b1ad5e",
            "Apache-2.0",
            "1579816840e7f7a694ef449c4d3d3d9a6e83001452e69a38b225df67e5851b7e",
        ),
        recipe=_recipe(run_id, training_examples), resources=_resources(run_id),
        environment_sha256=environment.manifest_sha256,
        maximum_wall_seconds=3_600,
        maximum_checkpoint_bytes=GIB,
        maximum_output_bytes=2 * GIB,
        one_use_job_id=f"{run_id}-job",
        lifetime_seconds=10_800, confirmed=True,
    )
    result = service.start(
        request_id=f"{run_id}-training-start",
        approval_id=approval.approval_id, confirmed=True,
    )
    if not isinstance(result, TrainingTerminalReceipt):
        raise RuntimeError(
            "specialist training admission denied: "
            + ",".join(result.reason_codes),
        )
    if result.status.value != "completed":
        raise RuntimeError(f"specialist training failed: {result.reason_code}")
    return CompletedSpecialistTraining(
        environment, approval, result, service.admissions(), service.jobs(),
        service.terminals(),
    )


def _recipe(run_id: str, training_examples: int) -> AdapterTrainingRecipe:
    epochs = 2.0
    batch_size = 1
    accumulation = 4
    return AdapterTrainingRecipe(
        recipe_id=f"{run_id}-qlora-r16-{training_examples}-chat-v2",
        method=AdapterTrainingMethod.QLORA,
        rank=16, alpha=32, dropout=0.05, target_modules=("all-linear",),
        base_weight_bits=4, quantization_type="nf4", double_quantization=True,
        compute_dtype=TrainingComputeDtype.BFLOAT16,
        maximum_sequence_tokens=1024, epochs=epochs,
        maximum_steps=math.ceil(
            training_examples * epochs / (batch_size * accumulation)
        ),
        per_device_batch_size=batch_size,
        gradient_accumulation_steps=accumulation,
        learning_rate=2e-4, seed=42,
    )


def _resources(run_id: str) -> TrainingResourceBudget:
    return TrainingResourceBudget(
        budget_id=f"{run_id}-resource-budget",
        maximum_cpu_cores=20,
        maximum_ram_bytes=32 * GIB,
        maximum_vram_bytes=13 * GIB,
        maximum_disk_bytes=12 * GIB,
        maximum_temperature_celsius=85,
        maximum_energy_joules=500_000,
        cgroup_policy_id="factory.training.specialist-checkpoint.v1",
    )
