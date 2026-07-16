#!/usr/bin/env python3
"""Replay Phase 7.4 admission for every reference expert and both profiles."""

import json
from pathlib import Path

from fam_os.scheduler.admission_contracts import (
    ResidentWeightEstimate,
    WeightEstimateSource,
)
from fam_os.scheduler.admission_inputs import build_admission_request
from fam_os.scheduler.admission_policy import DeterministicAdmissionPolicy
from fam_os.scheduler.residency_contracts import (
    ExpertResidencyIdentity,
    initial_cold_residency_catalog,
)
from fam_os.schemas import dumps_document, loads_document


ROOT = Path(__file__).resolve().parents[1]
CONTEXT = ROOT / "artifacts/scheduler/phase7.2/reference-context-estimates"
OUTPUT = ROOT / "artifacts/scheduler/phase7.4/reference-admission-replay"
OBSERVATIONS = {
    "compat": ROOT / "artifacts/scheduler/phase7.1/compat-observations-canonical/observation-2.json",
    "full": ROOT / "artifacts/scheduler/phase7.1/full-observations-canonical/observation-2.json",
}


def main() -> int:
    config = json.loads((ROOT / "configs/admission/reference-weight-estimates.json").read_text())
    entries = config["entries"]
    identities = tuple(
        ExpertResidencyIdentity(item["expert_id"], item["runtime_artifact_id"])
        for item in entries
    )
    OUTPUT.mkdir(parents=True, exist_ok=True)
    summary = {"schema_version": 1, "weight_policy": config["policy"], "profiles": []}
    policy = DeterministicAdmissionPolicy()
    for profile_name, path in OBSERVATIONS.items():
        observation = loads_document(path.read_text())
        catalog = initial_cold_residency_catalog(
            f"catalog.phase7.4.{profile_name}", identities, observation.observed_at
        )
        for entry in entries:
            result = _replay(profile_name, entry, observation, catalog, policy)
            summary["profiles"].append(result)
    (OUTPUT / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0


def _replay(profile_name, entry, observation, catalog, policy):
    expert_id = entry["expert_id"]
    profile_id = expert_id.removeprefix("expert.")
    context = loads_document((CONTEXT / f"context.{profile_id}.estimate.json").read_text())
    weight = ResidentWeightEstimate(
        expert_id, entry["runtime_artifact_id"], entry["resident_weight_bytes"],
        WeightEstimateSource.DECLARED_CONSERVATIVE,
        "artifact storage_bytes plus 10 percent weight-runtime expansion",
    )
    request = build_admission_request(
        f"admission.{profile_name}.{profile_id}", expert_id, observation,
        catalog, weight, context, {},
    )
    decision = policy.decide(f"decision.{profile_name}.{profile_id}", request)
    stem = f"{profile_name}-{profile_id}"
    (OUTPUT / f"{stem}.request.json").write_text(dumps_document(request) + "\n")
    (OUTPUT / f"{stem}.decision.json").write_text(dumps_document(decision) + "\n")
    return {
        "profile": profile_name,
        "expert_id": expert_id,
        "model_ref": entry["runtime_artifact_id"],
        "status": decision.status.value,
        "weight_bytes": decision.weight_increment_bytes,
        "context_bytes": decision.context_increment_bytes,
        "total_increment_bytes": decision.total_increment_bytes,
        "available_before_bytes": decision.available_before_bytes,
        "reason_codes": list(decision.reason_codes),
    }


if __name__ == "__main__":
    raise SystemExit(main())
