"""Deterministic repeated-sample drift evaluation for live adaptation."""

from __future__ import annotations

import hashlib
import math
from datetime import datetime

from fam_os.adaptation import (
    AdaptationHealthSample,
    AdaptationHealthSummary,
    LiveAdaptationDriftReport,
)


MINIMUM_HEALTH_SAMPLES = 2
MAXIMUM_ADAPTATION_TEMPERATURE_C = 85.0


def summarize_health(
    samples: tuple[AdaptationHealthSample, ...],
) -> AdaptationHealthSummary | None:
    if len(samples) < MINIMUM_HEALTH_SAMPLES:
        return None
    ordered = tuple(sorted(samples, key=lambda item: (item.observed_at, item.sample_id)))
    snapshot_ids = {item.snapshot_id for item in ordered}
    workflows = {item.workflow_id for item in ordered}
    if len(snapshot_ids) != 1 or len(workflows) != 1:
        raise ValueError("adaptation health summary requires one snapshot and workflow")
    temperatures = tuple(
        item.peak_temperature_c
        for item in ordered if item.peak_temperature_c is not None
    )
    evidence = "\n".join(
        f"{item.sample_id}|{item.verification_quality:.12g}|"
        f"{item.latency_seconds:.12g}|{item.peak_temperature_c}|"
        f"{int(item.policy_conformant)}"
        for item in ordered
    )
    return AdaptationHealthSummary(
        next(iter(snapshot_ids)), next(iter(workflows)), len(ordered),
        sum(item.verification_quality for item in ordered) / len(ordered),
        _percentile(tuple(item.latency_seconds for item in ordered), .95),
        max(temperatures) if temperatures else None,
        len(temperatures),
        sum(not item.policy_conformant for item in ordered),
        tuple(item.sample_id for item in ordered),
        hashlib.sha256(evidence.encode("utf-8")).hexdigest(),
    )


def evaluate_live_drift(
    baseline: AdaptationHealthSummary,
    candidate: AdaptationHealthSummary,
    evaluated_at: datetime,
) -> LiveAdaptationDriftReport:
    if baseline.workflow_id != candidate.workflow_id:
        raise ValueError("adaptation drift baselines must share one workflow")
    reasons: list[str] = []
    evaluated = ["verification_quality", "latency", "policy"]
    unavailable: list[str] = []
    if candidate.verification_quality < baseline.verification_quality:
        reasons.append("verification.quality_regressed")
    if candidate.p95_latency_seconds > baseline.p95_latency_seconds * 1.1:
        reasons.append("latency.p95_regressed")
    _evaluate_thermal(baseline, candidate, reasons, evaluated, unavailable)
    if (
        candidate.policy_violation_count > 0
        or candidate.policy_violation_count > baseline.policy_violation_count
    ):
        reasons.append("policy.violation_detected")
    identity = "\0".join((
        baseline.snapshot_id, candidate.snapshot_id,
        baseline.source_evidence_sha256, candidate.source_evidence_sha256,
    ))
    return LiveAdaptationDriftReport(
        f"live-drift-{hashlib.sha256(identity.encode('utf-8')).hexdigest()}",
        baseline.workflow_id, baseline, candidate,
        tuple(evaluated), tuple(unavailable), tuple(reasons), bool(reasons), evaluated_at,
    )


def _evaluate_thermal(baseline, candidate, reasons, evaluated, unavailable) -> None:
    candidate_temperature = candidate.max_temperature_c
    if candidate_temperature is None:
        unavailable.append("thermal")
        return
    evaluated.append("thermal")
    if candidate_temperature > MAXIMUM_ADAPTATION_TEMPERATURE_C:
        reasons.append("thermal.limit_exceeded")
    baseline_temperature = baseline.max_temperature_c
    if (
        baseline_temperature is not None
        and candidate_temperature > baseline_temperature + 5
    ):
        reasons.append("thermal.regressed")


def _percentile(values: tuple[float, ...], quantile: float) -> float:
    ordered = tuple(sorted(values))
    index = max(0, math.ceil(len(ordered) * quantile) - 1)
    return ordered[index]
