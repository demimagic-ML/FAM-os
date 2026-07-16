#!/usr/bin/env python3
"""Observe reference model metadata and emit strict context-memory estimates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from fam_os.adapters.ollama import (
    OllamaContextProfileObserver,
    OllamaContextProfilePolicy,
    OllamaSettings,
)
from fam_os.adapters.ollama.transport import UrllibJsonTransport
from fam_os.scheduler import (
    ContextMemoryEstimator,
    ContextMemoryReservation,
    ContextMemoryStrategy,
)
from fam_os.schemas import encode_document


ENTRY_FIELDS = {
    "profile_id", "expert_id", "model_ref", "strategy",
    "maximum_context_tokens", "input_token_upper_bound",
    "output_token_reservation",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:11434")
    args = parser.parse_args()
    config = _load_config(args.config)
    args.output.mkdir(parents=True, exist_ok=False)
    observer = OllamaContextProfileObserver(
        OllamaSettings(args.base_url, 30), UrllibJsonTransport()
    )
    summaries = []
    for index, entry in enumerate(config["entries"], start=1):
        profile, reservation, estimate = _estimate_entry(
            observer, ContextMemoryEstimator(), config, entry, index
        )
        stem = entry["profile_id"]
        _write(args.output / f"{stem}.profile.json", encode_document(profile))
        _write(args.output / f"{stem}.reservation.json", encode_document(reservation))
        _write(args.output / f"{stem}.estimate.json", encode_document(estimate))
        summaries.append({
            "profile_id": profile.profile_id,
            "expert_id": profile.expert_id,
            "model_ref": profile.runtime_artifact_id,
            "architecture": profile.architecture,
            "strategy": profile.strategy.value,
            "tokens_per_sequence": estimate.tokens_per_sequence,
            "total_context_bytes": estimate.total_context_bytes,
            "assumption_codes": list(estimate.assumption_codes),
            "model_resident_bytes_excluded": estimate.model_resident_bytes_excluded,
        })
    report = {"schema_version": 1, "profiles": summaries}
    _write(args.output / "summary.json", report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


def _estimate_entry(observer, estimator, config, entry, index):
    strategy = ContextMemoryStrategy(entry["strategy"])
    policy = OllamaContextProfilePolicy(
        entry["profile_id"], entry["expert_id"], entry["model_ref"], strategy,
        entry["maximum_context_tokens"], config["scalar_bytes"],
        config["fixed_runtime_overhead_bytes"],
        config["per_sequence_workspace_bytes"],
        config["safety_margin_basis_points"],
    )
    profile = observer.observe(policy)
    reservation = ContextMemoryReservation(
        f"reference-reservation-{index}", profile.profile_id,
        entry["input_token_upper_bound"], entry["output_token_reservation"],
    )
    estimate = estimator.estimate(f"reference-estimate-{index}", profile, reservation)
    return profile, reservation, estimate


def _load_config(path):
    payload = json.loads(path.read_text(encoding="utf-8"))
    expected = {
        "schema_version", "scalar_bytes", "fixed_runtime_overhead_bytes",
        "per_sequence_workspace_bytes", "safety_margin_basis_points", "entries",
    }
    if not isinstance(payload, dict) or set(payload) != expected:
        raise ValueError("context profile config fields are invalid")
    if payload["schema_version"] != 1 or not isinstance(payload["entries"], list):
        raise ValueError("context profile config version or entries are invalid")
    for entry in payload["entries"]:
        if not isinstance(entry, dict) or set(entry) != ENTRY_FIELDS:
            raise ValueError("context profile entry fields are invalid")
    return payload


def _write(path, payload):
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
