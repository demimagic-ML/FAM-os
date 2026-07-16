#!/usr/bin/env python3
"""Run a durable cold/warm/active/evicting lifecycle on isolated Ollama."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fam_os.adapters.filesystem import JsonExpertResidencyRepository
from fam_os.core.ports.inference import (
    InferenceMessage,
    InferenceRequest,
    MessageRole,
)
from fam_os.scheduler import (
    ExpertResidencyIdentity,
    ExpertResidencyService,
    ResidencyLease,
    initial_cold_residency_catalog,
)
from fam_os.schemas import encode_document
from tools.parity.composition import load_benchmark_composition
from tools.parity.profile_service import ProfiledOllamaService, ProfiledServiceSettings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--budget", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:11512")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    composition = load_benchmark_composition(args.profile, args.budget)
    settings = ProfiledServiceSettings(
        args.base_url, 120, composition, service_id="fam-residency-smoke"
    )
    report = _run(output, settings)
    _write(output / "summary.json", report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


def _run(output: Path, settings: ProfiledServiceSettings) -> dict[str, object]:
    now = datetime.now(timezone.utc)
    repository = JsonExpertResidencyRepository(output / "residency-state.json")
    initial = repository.initialize(initial_cold_residency_catalog(
        "live-residency-catalog",
        (ExpertResidencyIdentity("expert.code.qwen2.5-coder-7b", "qwen2.5-coder:7b"),),
        now,
    ))
    service = ExpertResidencyService(repository)
    snapshots = [("cold", initial)]
    with ProfiledOllamaService(settings) as ollama:
        ollama.runtime.chat(_load_request())
        warm = service.reconcile(
            ollama.runtime.loaded_models(), _after(now, 1), initial.revision
        )
        snapshots.append(("warm", warm))
        lease = ResidencyLease(
            "live-lease", "live-request", _after(now, 2), _after(now, 62)
        )
        active = service.acquire(
            "expert.code.qwen2.5-coder-7b", lease, warm.revision
        )
        snapshots.append(("active", active))
        released = service.release(
            "expert.code.qwen2.5-coder-7b", lease.lease_id,
            _after(now, 3), active.revision,
        )
        snapshots.append(("warm-released", released))
        evicting = service.begin_eviction(
            "expert.code.qwen2.5-coder-7b", "live-eviction",
            _after(now, 4), released.revision,
        )
        snapshots.append(("evicting", evicting))
        ollama.runtime.unload("qwen2.5-coder:7b")
        cold = service.confirm_eviction(
            "expert.code.qwen2.5-coder-7b", "live-eviction",
            _after(now, 5), evicting.revision,
        )
        snapshots.append(("cold-confirmed", cold))
        provider_absent = all(
            item.model_ref != "qwen2.5-coder:7b"
            for item in ollama.runtime.loaded_models()
        )
        resource = ollama.snapshot()
    for name, catalog in snapshots:
        _write(output / f"{name}.json", encode_document(catalog))
    return _report(settings, repository, ollama, snapshots, provider_absent, resource)


def _report(settings, repository, ollama, snapshots, provider_absent, resource):
    states = [catalog.require("expert.code.qwen2.5-coder-7b").state.value for _, catalog in snapshots]
    return {
        "schema_version": 1,
        "validation_profile_id": settings.composition.profile.profile_id,
        "states": states,
        "revisions": [catalog.revision for _, catalog in snapshots],
        "provider_absent_before_cold": provider_absent,
        "final_state": states[-1],
        "final_file_revision": repository.read().revision,
        "service_memory_peak_bytes": None if resource is None else resource.memory_peak_bytes,
        "service_cpu_usage_microseconds": None if resource is None else resource.cpu_usage_microseconds,
        "service_final_state": ollama.lifecycle.status(settings.service_id).state.value,
    }


def _load_request() -> InferenceRequest:
    return InferenceRequest(
        "qwen2.5-coder:7b",
        (InferenceMessage(MessageRole.USER, "Reply with the single word ready."),),
        512, 8, keep_alive="5m",
    )


def _after(value: datetime, seconds: int) -> datetime:
    return value + timedelta(seconds=seconds)


def _write(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
