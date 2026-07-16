#!/usr/bin/env python3
"""Capture two real cgroup-aware scheduler observations for one profile budget."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fam_os.adapters.cgroup import CgroupV2ResourceObserver
from fam_os.adapters.linux import (
    CacheDirectory,
    DirectoryStorageRuntimeObserver,
    NvidiaAcceleratorRuntimeObserver,
)
from fam_os.adapters.linux.command import SubprocessCommandRunner
from fam_os.adapters.systemd import SystemdUserServiceLifecycle
from fam_os.scheduler import EffectiveResourceBudget, LiveResourceSampler
from fam_os.schemas import encode_document, loads_document
from fam_os.supervisor import ResourceLimits, ServiceDefinition


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--budget", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--interval", type=float, default=0.5)
    args = parser.parse_args()
    if args.interval <= 0:
        parser.error("--interval must be positive")
    budget = _load_budget(args.budget)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    report = _capture(budget, args.budget.resolve(), output, args.interval)
    _write(output / "summary.json", report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


def _capture(budget, budget_path, output, interval):
    runner = SubprocessCommandRunner()
    lifecycle = SystemdUserServiceLifecycle(runner)
    service_id = f"fam-live-resources-{uuid4().hex[:8]}"
    definition = ServiceDefinition(
        service_id,
        ("/usr/bin/dd", "if=/dev/zero", "of=/dev/null", "bs=1M"),
        limits=ResourceLimits(
            budget.memory.effective_limit_bytes,
            budget.memory.swap_limit_bytes,
            budget.cpu.scheduler_quota_cores * 100,
            8,
        ),
    )
    cache = DirectoryStorageRuntimeObserver(tuple(
        CacheDirectory(item.storage_id, output) for item in budget.storage
    ))
    sampler = LiveResourceSampler(
        budget, CgroupV2ResourceObserver(lifecycle),
        NvidiaAcceleratorRuntimeObserver(runner), cache,
        service_id, (), lambda: datetime.now(timezone.utc),
        lambda: f"live.{uuid4().hex}",
    )
    try:
        lifecycle.start(definition)
        first = sampler.sample()
        time.sleep(interval)
        second = sampler.sample(first)
        _write(output / "observation-1.json", encode_document(first))
        _write(output / "observation-2.json", encode_document(second))
    finally:
        final_status = lifecycle.stop(service_id)
    return {
        "schema_version": 1,
        "budget_id": budget.budget_id,
        "validation_profile_id": budget.validation_profile.profile_id,
        "budget_source_sha256": hashlib.sha256(budget_path.read_bytes()).hexdigest(),
        "service_id": service_id,
        "service_final_state": final_status.state.value,
        "first_status": first.status.value,
        "second_status": second.status.value,
        "sequence_linked": second.previous_observation_id == first.observation_id,
        "cpu_usage_delta_microseconds": second.cpu.usage_delta_microseconds,
        "memory_scope_authoritative": second.memory.scope_authoritative,
        "memory_available_for_new_bytes": second.memory.available_for_new_bytes,
        "accelerator_placement": {
            item.device_id: item.placement_allowed for item in second.accelerators
        },
        "reason_codes": list(second.reason_codes),
    }


def _load_budget(path: Path) -> EffectiveResourceBudget:
    value = loads_document(path.read_text(encoding="utf-8"))
    if not isinstance(value, EffectiveResourceBudget):
        raise TypeError("budget path did not decode to an effective resource budget")
    return value


def _write(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
