"""Read-only full-workstation evidence around one fresh benchmark service."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from fam_os.adapters.linux.command import CommandRunner, SubprocessCommandRunner
from fam_os.adapters.linux.block_io import BlockIoReading, query_root_block_io
from fam_os.adapters.linux.nvidia import NvidiaResourceReading, query_nvidia_resources
from fam_os.core.ports.inference import LoadedModel
from fam_os.supervisor import ResourceSnapshot
from tools.parity.profile_service import ProfiledOllamaService
from tools.parity.serialization import loaded_models_payload, resource_payload


@dataclass(frozen=True, slots=True)
class EvidencePoint:
    captured_at: str
    resource: ResourceSnapshot | None
    accelerators: tuple[NvidiaResourceReading, ...]
    loaded_models: tuple[LoadedModel, ...]
    storage_io: BlockIoReading | None


@dataclass(slots=True)
class WorkstationEvidenceCollector:
    runner: CommandRunner = field(default_factory=SubprocessCommandRunner)
    _before: EvidencePoint | None = None

    def capture_before(self, service: ProfiledOllamaService) -> None:
        self._before = _capture(service, self.runner)

    def finish(
        self,
        service: ProfiledOllamaService,
        loaded: tuple[LoadedModel, ...],
        resources: ResourceSnapshot | None,
    ) -> dict[str, object]:
        if self._before is None:
            raise RuntimeError("workstation evidence requires a before point")
        after = EvidencePoint(
            _captured_at(),
            resources,
            query_nvidia_resources(self.runner),
            loaded,
            query_root_block_io(self.runner),
        )
        return _evidence_payload(self._before, after)


def _capture(
    service: ProfiledOllamaService, runner: CommandRunner
) -> EvidencePoint:
    return EvidencePoint(
        _captured_at(),
        service.snapshot(),
        query_nvidia_resources(runner),
        service.runtime.loaded_models(),
        query_root_block_io(runner),
    )


def _evidence_payload(before: EvidencePoint, after: EvidencePoint) -> dict[str, object]:
    return {
        "schema_version": 1,
        "sampling_method": "fresh_service_before_after",
        "before": _point_payload(before),
        "after": _point_payload(after),
        "deltas": _resource_deltas(before.resource, after.resource),
        "accelerator_deltas": _accelerator_deltas(before, after),
        "model_transfers": _model_transfers(before.loaded_models, after.loaded_models),
        "storage_io_delta": _storage_delta(before.storage_io, after.storage_io),
        "measurement_availability": _measurement_availability(after),
    }


def _point_payload(point: EvidencePoint) -> dict[str, object]:
    return {
        "captured_at": point.captured_at,
        "service_resources": resource_payload(point.resource),
        "accelerators": [_accelerator_payload(item) for item in point.accelerators],
        "loaded_models": loaded_models_payload(point.loaded_models),
        "storage_io": _storage_payload(point.storage_io),
    }


def _accelerator_payload(reading: NvidiaResourceReading) -> dict[str, object]:
    return {
        "device_id": f"gpu-{reading.index}",
        "name": reading.name,
        "memory_total_bytes": reading.memory_total_bytes,
        "memory_used_bytes": reading.memory_used_bytes,
        "utilization_fraction": reading.utilization_fraction,
        "driver_version": reading.driver_version,
    }


def _resource_deltas(
    before: ResourceSnapshot | None, after: ResourceSnapshot | None
) -> dict[str, int | None]:
    names = (
        "cpu_usage_microseconds",
        "cpu_user_microseconds",
        "cpu_system_microseconds",
        "io_read_bytes",
        "io_write_bytes",
        "io_read_operations",
        "io_write_operations",
    )
    return {name: _delta(before, after, name) for name in names}


def _delta(
    before: ResourceSnapshot | None, after: ResourceSnapshot | None, name: str
) -> int | None:
    old = getattr(before, name, None)
    new = getattr(after, name, None)
    if old is None or new is None:
        return None
    return max(0, new - old)


def _accelerator_deltas(
    before: EvidencePoint, after: EvidencePoint
) -> list[dict[str, object]]:
    old = {item.index: item for item in before.accelerators}
    return [
        {
            "device_id": f"gpu-{item.index}",
            "memory_used_delta_bytes": item.memory_used_bytes
            - old.get(item.index, item).memory_used_bytes,
            "max_observed_memory_used_bytes": max(
                item.memory_used_bytes, old.get(item.index, item).memory_used_bytes
            ),
            "sample_count": 2,
        }
        for item in after.accelerators
    ]


def _model_transfers(
    before: tuple[LoadedModel, ...], after: tuple[LoadedModel, ...]
) -> list[dict[str, object]]:
    old = {item.model_ref: item for item in before}
    return [
        {
            "model_ref": item.model_ref,
            "resident_set_delta_bytes": _model_delta(item.resident_bytes, old.get(item.model_ref)),
            "accelerator_residency_delta_bytes": _model_delta(
                item.accelerator_bytes, old.get(item.model_ref), accelerator=True
            ),
            "evidence_kind": "fresh_service_residency_delta",
        }
        for item in after
    ]


def _model_delta(
    value: int | None, old: LoadedModel | None, *, accelerator: bool = False
) -> int | None:
    if value is None:
        return None
    previous = 0 if old is None else (
        old.accelerator_bytes if accelerator else old.resident_bytes
    )
    return None if previous is None else max(0, value - previous)


def _measurement_availability(point: EvidencePoint) -> dict[str, bool]:
    resource = point.resource
    return {
        "cpu": resource is not None and resource.cpu_usage_microseconds is not None,
        "ram": resource is not None and resource.memory_peak_bytes is not None,
        "vram": bool(point.accelerators),
        "model_transfers": bool(point.loaded_models),
        "ssd_io": (resource is not None and resource.io_read_bytes is not None)
        or point.storage_io is not None,
    }


def _storage_payload(reading: BlockIoReading | None) -> dict[str, object] | None:
    if reading is None:
        return None
    return {
        "storage_id": reading.storage_id,
        "read_bytes": reading.read_bytes,
        "write_bytes": reading.write_bytes,
        "read_operations": reading.read_operations,
        "write_operations": reading.write_operations,
        "scope": reading.scope,
    }


def _storage_delta(
    before: BlockIoReading | None, after: BlockIoReading | None
) -> dict[str, object] | None:
    if before is None or after is None:
        return None
    return {
        "storage_id": after.storage_id,
        "read_bytes": max(0, after.read_bytes - before.read_bytes),
        "write_bytes": max(0, after.write_bytes - before.write_bytes),
        "read_operations": max(0, after.read_operations - before.read_operations),
        "write_operations": max(0, after.write_operations - before.write_operations),
        "scope": after.scope,
        "attribution": "host_activity_during_benchmark_window",
    }


def _captured_at() -> str:
    return datetime.now(timezone.utc).isoformat()
