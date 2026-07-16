"""Continuous benchmark and regression gating."""

from dataclasses import dataclass

FACTORY_REGRESSION_CONTRACT_VERSION = "fam.factory.regression/v1alpha1"


@dataclass(frozen=True, slots=True)
class RegressionGateResult:
    gate_id: str
    baseline_quality: float
    candidate_quality: float
    maximum_latency_seconds: float
    observed_latency_seconds: float
    maximum_energy_joules: float
    observed_energy_joules: float
    acceptance_passed: bool
    passed: bool
    reason_codes: tuple[str, ...]
    contract_version: str = FACTORY_REGRESSION_CONTRACT_VERSION


def evaluate_regression(gate_id, baseline_quality, candidate_quality,
                        max_latency, latency, max_energy, energy, acceptance):
    reasons = []
    if candidate_quality < baseline_quality:
        reasons.append("quality.regressed")
    if latency > max_latency:
        reasons.append("latency.exceeded")
    if energy > max_energy:
        reasons.append("energy.exceeded")
    if not acceptance:
        reasons.append("acceptance.failed")
    return RegressionGateResult(gate_id, baseline_quality, candidate_quality,
                                max_latency, latency, max_energy, energy,
                                acceptance, not reasons, tuple(reasons))
