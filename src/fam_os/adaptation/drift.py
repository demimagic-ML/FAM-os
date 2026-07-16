"""Adaptation drift detection and immutable rollback evidence."""

from dataclasses import dataclass

ADAPTATION_DRIFT_CONTRACT_VERSION = "fam.adaptation.drift/v1alpha1"


@dataclass(frozen=True, slots=True)
class AdaptationSnapshot:
    snapshot_id: str
    payload_sha256: str
    verification_quality: float
    latency_seconds: float
    energy_joules: float

    def __post_init__(self) -> None:
        if len(self.payload_sha256) != 64 or not 0 <= self.verification_quality <= 1:
            raise ValueError("adaptation snapshot digest or quality is invalid")
        if self.latency_seconds <= 0 or self.energy_joules <= 0:
            raise ValueError("adaptation snapshot resources must be positive")


@dataclass(frozen=True, slots=True)
class AdaptationDriftReport:
    baseline_snapshot_id: str
    candidate_snapshot_id: str
    reason_codes: tuple[str, ...]
    drifted: bool
    contract_version: str = ADAPTATION_DRIFT_CONTRACT_VERSION


@dataclass(frozen=True, slots=True)
class AdaptationRollbackReceipt:
    rejected_snapshot_id: str
    restored_snapshot_id: str
    restored_payload_sha256: str
    applied: bool
    contract_version: str = ADAPTATION_DRIFT_CONTRACT_VERSION


class AdaptationDriftPolicy:
    def evaluate(self, baseline: AdaptationSnapshot, candidate: AdaptationSnapshot):
        reasons = []
        if candidate.verification_quality < baseline.verification_quality:
            reasons.append("verification.quality-regressed")
        if candidate.latency_seconds > baseline.latency_seconds * 1.1:
            reasons.append("latency.regressed")
        if candidate.energy_joules > baseline.energy_joules * 1.1:
            reasons.append("energy.regressed")
        return AdaptationDriftReport(
            baseline.snapshot_id, candidate.snapshot_id, tuple(reasons), bool(reasons),
        )

    def rollback(self, baseline, candidate, report):
        if not report.drifted or report.baseline_snapshot_id != baseline.snapshot_id:
            raise ValueError("rollback requires matching detected drift")
        return AdaptationRollbackReceipt(
            candidate.snapshot_id, baseline.snapshot_id, baseline.payload_sha256, True,
        )
