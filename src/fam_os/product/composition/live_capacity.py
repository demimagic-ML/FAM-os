"""Production host capacity derived from live policy and enforced limits."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from fam_os.adaptation.resource_policy import OperatingStatePolicy
from fam_os.adapters.linux.command import CommandRunner, SubprocessCommandRunner
from fam_os.adapters.linux.nvidia import NvidiaResourceReading, query_nvidia_resources
from fam_os.adapters.linux.operating_state import LinuxOperatingStateObserver
from fam_os.core.production.model_selection import HostCapacity
from fam_os.scheduler import AcceleratorVisibility, ValidationProfileDocument
from fam_os.supervisor import ResourceSnapshot


_GIBIBYTE = 1024**3
_FULL_HOST_THRESHOLD = 32 * _GIBIBYTE
_FULL_HOST_RESERVE = 12 * _GIBIBYTE
_COMPAT_HOST_RESERVE = 2 * _GIBIBYTE
_FULL_VRAM_RESERVE = _GIBIBYTE


@dataclass(slots=True)
class ProductCapacityObserver:
    """Project authoritative Linux readings into the production selector."""

    meminfo_path: Path = Path("/proc/meminfo")
    runner: CommandRunner = field(default_factory=SubprocessCommandRunner)
    operating_state: LinuxOperatingStateObserver | None = None
    managed_resource_snapshot: Callable[[], ResourceSnapshot | None] | None = None
    policy: OperatingStatePolicy = field(default_factory=OperatingStatePolicy)
    validation_profile: ValidationProfileDocument | None = None

    def __post_init__(self) -> None:
        if self.operating_state is None:
            self.operating_state = LinuxOperatingStateObserver(self.runner)

    def observe(self) -> HostCapacity:
        total, available = _meminfo(self.meminfo_path)
        profile_ceiling = None
        profile_reasons: tuple[str, ...]
        if self.validation_profile is None:
            full_host = total > _FULL_HOST_THRESHOLD
            host_reserve = _FULL_HOST_RESERVE if full_host else _COMPAT_HOST_RESERVE
            readings = query_nvidia_resources(self.runner)
            vram = max(
                (item.memory_total_bytes - item.memory_used_bytes for item in readings),
                default=0,
            )
            vram_reserve = _FULL_VRAM_RESERVE if full_host and vram else 0
            profile_reasons = (
                "profile.full-reference-workstation"
                if full_host else "profile.compat-cpu-16gb",
            )
        else:
            profile = self.validation_profile
            resource_policy = profile.configuration.policy
            host_reserve = resource_policy.memory_headroom_bytes
            profile_ceiling = resource_policy.max_memory_bytes
            if (
                profile.service.accelerator_visibility
                is AcceleratorVisibility.DENY_ALL
            ):
                vram = 0
                vram_reserve = 0
                visibility_reason = "accelerator.visibility.denied"
            else:
                readings = query_nvidia_resources(self.runner)
                vram, vram_reserve = _profiled_vram(readings, profile)
                visibility_reason = "accelerator.visibility.discovered"
            profile_reasons = (
                f"profile.{profile.profile_id}", visibility_reason,
            )
        if self.operating_state is None:  # pragma: no cover - guarded by __post_init__
            raise RuntimeError("operating-state observer was not composed")
        operating = self.operating_state.observe()
        decision = self.policy.decide(operating.state)
        incomplete_state = "battery.reading_unavailable" in operating.reason_codes
        cgroup_ceiling, cgroup_reasons = self._cgroup_ceiling()
        ceiling = _minimum_ceiling(profile_ceiling, cgroup_ceiling)
        reasons = tuple(dict.fromkeys(
            profile_reasons + operating.reason_codes
            + decision.reason_codes + cgroup_reasons
        ))
        return HostCapacity(
            available_host_bytes=available,
            available_vram_bytes=vram,
            reserved_host_bytes=host_reserve,
            reserved_vram_bytes=vram_reserve,
            host_allocation_ceiling_bytes=ceiling,
            maximum_expert_tier=decision.maximum_expert_tier.value,
            speculative_prefetch_allowed=(
                decision.speculative_prefetch_allowed and not incomplete_state
            ),
            background_adaptation_allowed=(
                decision.background_adaptation_allowed and not incomplete_state
            ),
            reason_codes=reasons,
        )

    def _cgroup_ceiling(self) -> tuple[int | None, tuple[str, ...]]:
        if self.managed_resource_snapshot is None:
            return None, ("cgroup.external_runtime",)
        try:
            snapshot = self.managed_resource_snapshot()
        except Exception:
            snapshot = None
        if snapshot is None:
            return 0, ("cgroup.managed_snapshot_unavailable",)
        limit = snapshot.memory_limit
        if limit is None or limit.maximum_bytes is None:
            return None, ("cgroup.managed_unbounded",)
        if snapshot.memory_current_bytes is None:
            return 0, ("cgroup.managed_usage_unavailable",)
        remaining = max(0, limit.maximum_bytes - snapshot.memory_current_bytes)
        return remaining, ("cgroup.managed_ceiling_applied",)


def observe_host_capacity() -> HostCapacity:
    """Compatibility entry point for callers without a composed observer."""

    return ProductCapacityObserver().observe()


def _meminfo(path: Path) -> tuple[int, int]:
    values: dict[str, int] = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            key, separator, remainder = line.partition(":")
            if separator and key in {"MemTotal", "MemAvailable"}:
                values[key] = int(remainder.split()[0]) * 1024
    except (OSError, ValueError, IndexError):
        pass
    if set(values) != {"MemTotal", "MemAvailable"}:
        raise RuntimeError("authoritative host memory capacity is unavailable")
    if values["MemTotal"] <= 0 or values["MemAvailable"] > values["MemTotal"]:
        raise RuntimeError("authoritative host memory capacity is invalid")
    return values["MemTotal"], values["MemAvailable"]


def _minimum_ceiling(first: int | None, second: int | None) -> int | None:
    ceilings = tuple(value for value in (first, second) if value is not None)
    return min(ceilings) if ceilings else None


def _profiled_vram(
    readings: tuple[NvidiaResourceReading, ...],
    profile: ValidationProfileDocument,
) -> tuple[int, int]:
    policy = profile.configuration.policy
    reserve = policy.accelerator_reserved_memory_bytes
    visible_capacities = []
    for item in readings:
        total = item.memory_total_bytes
        free = max(0, total - item.memory_used_bytes)
        requested = int(total * policy.accelerator_memory_fraction)
        if policy.max_accelerator_memory_bytes is not None:
            requested = min(requested, policy.max_accelerator_memory_bytes)
        scheduler_limit = min(requested, max(0, total - reserve))
        visible_capacities.append(min(free, scheduler_limit + reserve))
    visible = max(visible_capacities, default=0)
    return visible, min(reserve, visible)
