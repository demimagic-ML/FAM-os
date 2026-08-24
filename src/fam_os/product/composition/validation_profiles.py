"""Installed validation-profile loading and production service translation."""

from __future__ import annotations

import os
from importlib.resources import files

from fam_os.scheduler import (
    AcceleratorVisibility,
    COMPAT_CPU_16GB_PROFILE_ID,
    FULL_REFERENCE_WORKSTATION_PROFILE_ID,
    ValidationProfileDocument,
)
from fam_os.schemas import loads_document
from fam_os.supervisor import ResourceLimits


SUPPORTED_VALIDATION_PROFILE_IDS = (
    COMPAT_CPU_16GB_PROFILE_ID,
    FULL_REFERENCE_WORKSTATION_PROFILE_ID,
)
_PROFILE_FILENAMES = {
    profile_id: f"{profile_id}.json"
    for profile_id in SUPPORTED_VALIDATION_PROFILE_IDS
}


def load_validation_profile(profile_id: str) -> ValidationProfileDocument:
    """Load one canonical strict profile from installed package resources."""

    filename = _PROFILE_FILENAMES.get(profile_id)
    if filename is None:
        raise ValueError(f"unsupported validation profile: {profile_id}")
    resource = files("fam_os.product.resources").joinpath("profiles", filename)
    value = loads_document(resource.read_text(encoding="utf-8"))
    if not isinstance(value, ValidationProfileDocument):
        raise TypeError("packaged validation profile decoded to the wrong domain type")
    if value.profile_id != profile_id:
        raise RuntimeError("packaged validation profile identity does not match its filename")
    return value


def validation_profile_resource_limits(
    profile: ValidationProfileDocument,
    logical_cpu_count: int | None = None,
) -> ResourceLimits:
    """Translate a profile into the managed inference service cgroup envelope."""

    cpu_count = logical_cpu_count if logical_cpu_count is not None else os.cpu_count()
    visible_cpu_count = cpu_count or 1
    policy = profile.configuration.policy
    if policy.reserved_logical_cpu_count >= visible_cpu_count:
        raise ValueError("validation profile CPU reserve leaves no schedulable CPU")
    scheduler_cpu_cores = min(
        visible_cpu_count * policy.cpu_quota_fraction,
        float(visible_cpu_count - policy.reserved_logical_cpu_count),
    )
    if policy.max_cpu_cores is not None:
        scheduler_cpu_cores = min(scheduler_cpu_cores, policy.max_cpu_cores)
    cpu_cores = (
        profile.service.cpu_quota_cores
        if profile.service.cpu_quota_cores is not None
        else scheduler_cpu_cores
    )
    memory_high = None
    if profile.service.memory_max_bytes is not None:
        memory_high = policy.max_memory_bytes
    return ResourceLimits(
        memory_max_bytes=profile.service.memory_max_bytes,
        swap_max_bytes=profile.service.swap_max_bytes,
        cpu_quota_percent=cpu_cores * 100,
        tasks_max=512,
        memory_high_bytes=memory_high,
    )


def validation_profile_accelerator_environment(
    profile: ValidationProfileDocument,
) -> tuple[tuple[str, str], ...]:
    """Return fail-closed provider settings for denied accelerator visibility."""

    if profile.service.accelerator_visibility is AcceleratorVisibility.DISCOVERED:
        return ()
    return (
        ("CUDA_VISIBLE_DEVICES", "-1"),
        ("GGML_VK_VISIBLE_DEVICES", "-1"),
        ("OLLAMA_VULKAN", "0"),
        ("OLLAMA_LLM_LIBRARY", "cpu_avx2"),
    )
