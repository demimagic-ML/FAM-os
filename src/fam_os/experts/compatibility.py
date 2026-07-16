"""Pure expert manifest compatibility evaluation against host and profile."""

from __future__ import annotations

from dataclasses import dataclass

from fam_os.experts.compatibility_contracts import (
    ExpertCompatibilityReport,
    ExpertCompatibilityStatus,
)
from fam_os.experts.manifest import ExpertManifest
from fam_os.scheduler.resources import EffectiveResourceBudget, HostInventory


@dataclass(frozen=True, slots=True)
class _AcceleratorEvaluation:
    current_ids: tuple[str, ...]
    profile_ids: tuple[str, ...]
    physical_ids: tuple[str, ...]


class ExpertCompatibilityEvaluator:
    def evaluate(
        self,
        manifest: ExpertManifest,
        inventory: HostInventory,
        budget: EffectiveResourceBudget,
    ) -> ExpertCompatibilityReport:
        _require_consistent_resources(inventory, budget)
        required_memory = max(
            manifest.resources.estimated_resident_bytes,
            manifest.resources.minimum_system_memory_bytes,
        )
        hard, current = _system_and_storage_reasons(
            manifest, inventory, budget, required_memory
        )
        accelerators = _accelerator_evaluation(manifest, inventory, budget)
        profile, accelerator_current, optional = _accelerator_reasons(
            manifest, accelerators
        )
        reasons = tuple(hard + profile + current + accelerator_current + optional)
        status = _status(hard, profile, current + accelerator_current, optional)
        storage_ids = tuple(
            sorted(
                item.storage_id
                for item in inventory.storage
                if item.available_bytes >= manifest.resources.storage_bytes
            )
        )
        package = manifest.package
        return ExpertCompatibilityReport(
            package.package_id,
            package.package_version,
            manifest.expert_id,
            inventory.inventory_id,
            budget.budget_id,
            budget.validation_profile.profile_id,
            status,
            required_memory,
            budget.memory.available_for_new_bytes,
            storage_ids,
            accelerators.current_ids,
            reasons,
        )


def _require_consistent_resources(
    inventory: HostInventory,
    budget: EffectiveResourceBudget,
) -> None:
    if budget.inventory_id != inventory.inventory_id:
        raise ValueError("expert compatibility budget references another inventory")
    accelerator_ids = {item.device_id for item in inventory.accelerators}
    storage_ids = {item.storage_id for item in inventory.storage}
    if any(item.device_id not in accelerator_ids for item in budget.accelerators):
        raise ValueError("expert compatibility budget has unknown accelerator")
    if any(item.storage_id not in storage_ids for item in budget.storage):
        raise ValueError("expert compatibility budget has unknown storage")


def _system_and_storage_reasons(manifest, inventory, budget, required):
    hard: list[str] = []
    current: list[str] = []
    architectures = manifest.resources.supported_architectures
    if architectures and inventory.cpu.architecture not in architectures:
        hard.append("hardware.cpu_architecture_unsupported")
    if inventory.memory.total_bytes < required:
        hard.append("hardware.system_memory_insufficient")
    elif budget.memory.scheduler_limit_bytes < required:
        hard.append("profile.system_memory_limit_insufficient")
    elif budget.memory.available_for_new_bytes < required:
        current.append("current.system_memory_busy")
    capacities = tuple(item.capacity_bytes for item in inventory.storage)
    available = tuple(item.available_bytes for item in inventory.storage)
    if not any(value >= manifest.resources.storage_bytes for value in capacities):
        hard.append("hardware.storage_capacity_insufficient")
    elif not any(value >= manifest.resources.storage_bytes for value in available):
        current.append("current.storage_space_insufficient")
    return hard, current


def _accelerator_evaluation(manifest, inventory, budget) -> _AcceleratorEvaluation:
    required = manifest.resources.minimum_accelerator_memory_bytes
    if required == 0:
        return _AcceleratorEvaluation((), (), ())
    physical = {
        item.device_id
        for item in inventory.accelerators
        if item.memory_total_bytes is not None and item.memory_total_bytes >= required
    }
    profile = {
        item.device_id
        for item in budget.accelerators
        if item.device_id in physical
        and item.placement_allowed
        and item.scheduler_memory_limit_bytes >= required
    }
    current = {
        item.device_id
        for item in budget.accelerators
        if item.device_id in profile
        and max(0, item.scheduler_memory_limit_bytes - item.current_memory_bytes) >= required
    }
    return _AcceleratorEvaluation(
        tuple(sorted(current)), tuple(sorted(profile)), tuple(sorted(physical))
    )


def _accelerator_reasons(manifest, result):
    required = manifest.resources.minimum_accelerator_memory_bytes
    if required == 0:
        return [], [], []
    if manifest.resources.accelerator_optional:
        if result.current_ids:
            return [], [], []
        reason = (
            "degradation.optional_accelerator_busy"
            if result.profile_ids
            else "degradation.optional_accelerator_unavailable"
        )
        return [], [], [reason]
    if not result.physical_ids:
        return ["hardware.required_accelerator_unavailable"], [], []
    if not result.profile_ids:
        return ["profile.required_accelerator_unavailable"], [], []
    if not result.current_ids:
        return [], ["current.required_accelerator_busy"], []
    return [], [], []


def _status(hard, profile, current, optional) -> ExpertCompatibilityStatus:
    if hard or profile:
        return ExpertCompatibilityStatus.INCOMPATIBLE
    if current:
        return ExpertCompatibilityStatus.CURRENTLY_CONSTRAINED
    if optional:
        return ExpertCompatibilityStatus.COMPATIBLE_CPU_ONLY
    return ExpertCompatibilityStatus.COMPATIBLE
