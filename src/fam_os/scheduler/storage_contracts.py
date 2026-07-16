"""SSD artifact, mmap page-cache, and bounded model-load I/O contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from fam_os.scheduler.resources import StorageMedium


STORAGE_PAGING_CONTRACT_VERSION = "fam.scheduler.storage-paging/v1alpha1"


class LoadCacheState(StrEnum):
    COLD = "cold"
    WARM = "warm"


@dataclass(frozen=True, slots=True)
class ModelStorageArtifact:
    artifact_id: str
    model_ref: str
    digest_sha256: str
    declared_bytes: int
    observed_file_bytes: int
    storage_id: str
    storage_medium: StorageMedium
    filesystem_type: str
    mmap_eligible: bool
    path_disclosed: bool
    storage_bytes_excluded_from_ram_capacity: bool
    contract_version: str = STORAGE_PAGING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != STORAGE_PAGING_CONTRACT_VERSION:
            raise ValueError("unsupported storage paging contract_version")
        for name in ("artifact_id", "model_ref", "storage_id", "filesystem_type"):
            _text(getattr(self, name), name)
        if len(self.digest_sha256) != 64:
            raise ValueError("storage artifact requires SHA-256 digest")
        if self.declared_bytes <= 0 or self.observed_file_bytes != self.declared_bytes:
            raise ValueError("storage artifact size is not provider-consistent")
        if not self.mmap_eligible or self.path_disclosed:
            raise ValueError("storage artifact must be mmap eligible and path private")
        if not self.storage_bytes_excluded_from_ram_capacity:
            raise ValueError("SSD artifact bytes cannot be represented as RAM")


@dataclass(frozen=True, slots=True)
class ArtifactCacheObservation:
    observation_id: str
    artifact_id: str
    observed_at: datetime
    file_bytes: int
    page_size_bytes: int
    page_count: int
    resident_page_count: int
    resident_bytes_upper_bound: int
    resident_fraction: float
    counted_in_cgroup_memory_when_mapped: bool
    contract_version: str = STORAGE_PAGING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != STORAGE_PAGING_CONTRACT_VERSION:
            raise ValueError("unsupported storage paging contract_version")
        _text(self.observation_id, "observation_id")
        _text(self.artifact_id, "artifact_id")
        _time(self.observed_at, "observed_at")
        if self.file_bytes <= 0 or self.page_size_bytes <= 0 or self.page_count <= 0:
            raise ValueError("cache observation dimensions must be positive")
        expected_pages = (self.file_bytes + self.page_size_bytes - 1) // self.page_size_bytes
        if self.page_count != expected_pages:
            raise ValueError("cache page count is inconsistent")
        if not 0 <= self.resident_page_count <= self.page_count:
            raise ValueError("resident page count is invalid")
        expected_bytes = min(self.file_bytes, self.resident_page_count * self.page_size_bytes)
        if self.resident_bytes_upper_bound != expected_bytes:
            raise ValueError("resident cache bytes are inconsistent")
        expected_fraction = self.resident_page_count / self.page_count
        if abs(self.resident_fraction - expected_fraction) > 1e-12:
            raise ValueError("resident cache fraction is inconsistent")
        if not self.counted_in_cgroup_memory_when_mapped:
            raise ValueError("mapped cache pages must remain memory-accounted")


@dataclass(frozen=True, slots=True)
class ModelLoadIoBudget:
    budget_id: str
    artifact_id: str
    maximum_physical_read_bytes: int
    maximum_physical_write_bytes: int
    read_bandwidth_limit_bytes_per_second: int | None
    write_bandwidth_limit_bytes_per_second: int | None
    kernel_bandwidth_controller_available: bool
    cumulative_process_io_enforced: bool

    def __post_init__(self) -> None:
        _text(self.budget_id, "budget_id")
        _text(self.artifact_id, "artifact_id")
        if self.maximum_physical_read_bytes <= 0 or self.maximum_physical_write_bytes < 0:
            raise ValueError("model-load I/O byte budgets are invalid")
        rates = (
            self.read_bandwidth_limit_bytes_per_second,
            self.write_bandwidth_limit_bytes_per_second,
        )
        if any(value is not None and value <= 0 for value in rates):
            raise ValueError("model-load I/O rates must be positive")
        if not self.cumulative_process_io_enforced:
            raise ValueError("model-load I/O requires cumulative enforcement")


@dataclass(frozen=True, slots=True)
class ModelLoadIoTrial:
    trial_id: str
    cache_state: LoadCacheState
    cache_before_load: ArtifactCacheObservation
    cache_after_load: ArtifactCacheObservation
    physical_read_bytes: int
    physical_write_bytes: int
    logical_read_bytes: int
    provider_load_seconds: float
    provider_resident_bytes: int
    service_memory_peak_bytes: int
    cache_eviction_requested: bool
    cache_eviction_effective: bool
    model_unloaded_after_trial: bool

    def __post_init__(self) -> None:
        _text(self.trial_id, "trial_id")
        if self.cache_before_load.artifact_id != self.cache_after_load.artifact_id:
            raise ValueError("load trial cache observations reference different artifacts")
        values = (
            self.physical_read_bytes, self.physical_write_bytes,
            self.logical_read_bytes, self.provider_resident_bytes,
            self.service_memory_peak_bytes,
        )
        if any(value < 0 for value in values):
            raise ValueError("load trial counters cannot be negative")
        if self.provider_load_seconds <= 0 or self.provider_resident_bytes <= 0:
            raise ValueError("load trial requires provider load evidence")
        if self.cache_state is LoadCacheState.COLD:
            if not self.cache_eviction_requested or not self.cache_eviction_effective:
                raise ValueError("cold load requires effective cache eviction")
        elif self.cache_eviction_requested or self.cache_eviction_effective:
            raise ValueError("warm load cannot claim cache eviction")
        if not self.model_unloaded_after_trial:
            raise ValueError("load trial requires confirmed unload")


@dataclass(frozen=True, slots=True)
class StoragePagingEvidence:
    evidence_id: str
    artifact: ModelStorageArtifact
    budget: ModelLoadIoBudget
    cache_before_eviction: ArtifactCacheObservation
    cold_trial: ModelLoadIoTrial
    warm_trial: ModelLoadIoTrial
    service_final_state: str
    final_loaded_model_refs: tuple[str, ...]
    contract_version: str = STORAGE_PAGING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != STORAGE_PAGING_CONTRACT_VERSION:
            raise ValueError("unsupported storage paging contract_version")
        _text(self.evidence_id, "evidence_id")
        if self.budget.artifact_id != self.artifact.artifact_id:
            raise ValueError("storage budget references another artifact")
        observations = (
            self.cache_before_eviction, self.cold_trial.cache_before_load,
            self.cold_trial.cache_after_load, self.warm_trial.cache_before_load,
            self.warm_trial.cache_after_load,
        )
        if any(item.artifact_id != self.artifact.artifact_id for item in observations):
            raise ValueError("storage evidence cache artifact mismatch")
        if self.cold_trial.physical_read_bytes > self.budget.maximum_physical_read_bytes:
            raise ValueError("cold load exceeded physical read budget")
        if self.warm_trial.physical_read_bytes > self.budget.maximum_physical_read_bytes:
            raise ValueError("warm load exceeded physical read budget")
        if max(self.cold_trial.physical_write_bytes, self.warm_trial.physical_write_bytes) > self.budget.maximum_physical_write_bytes:
            raise ValueError("model load exceeded physical write budget")
        if self.warm_trial.physical_read_bytes > self.cold_trial.physical_read_bytes:
            raise ValueError("warm load cannot read more physical bytes than cold load")
        if self.service_final_state != "inactive" or self.final_loaded_model_refs:
            raise ValueError("storage evidence requires inactive unloaded cleanup")


def _text(value: str, name: str) -> None:
    if not value.strip():
        raise ValueError(f"{name} must not be empty")


def _time(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
