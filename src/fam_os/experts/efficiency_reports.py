"""Measured expert quality and resource-efficiency selection reports."""

from dataclasses import dataclass
from enum import StrEnum

EFFICIENCY_REPORT_CONTRACT_VERSION = "fam.expert.efficiency-report/v1alpha1"


class EfficiencyMetric(StrEnum):
    QUALITY_PER_BYTE = "quality_per_byte"
    QUALITY_PER_SECOND = "quality_per_second"
    QUALITY_PER_JOULE = "quality_per_joule"


@dataclass(frozen=True, slots=True)
class PowerSample:
    offset_seconds: float
    watts: float


@dataclass(frozen=True, slots=True)
class ExpertEfficiencyMeasurement:
    expert_id: str
    model_ref: str
    artifact_sha256: str
    quality_score: float
    artifact_bytes: int
    wall_seconds: float
    energy_joules: float
    power_samples: tuple[PowerSample, ...]

    def __post_init__(self) -> None:
        if not 0 <= self.quality_score <= 1:
            raise ValueError("quality score must be between zero and one")
        if self.artifact_bytes <= 0 or self.wall_seconds <= 0 or self.energy_joules <= 0:
            raise ValueError("efficiency resources must be measured and positive")
        if len(self.power_samples) < 2:
            raise ValueError("energy requires at least two raw power samples")

    def value(self, metric: EfficiencyMetric) -> float:
        denominator = {
            EfficiencyMetric.QUALITY_PER_BYTE: self.artifact_bytes,
            EfficiencyMetric.QUALITY_PER_SECOND: self.wall_seconds,
            EfficiencyMetric.QUALITY_PER_JOULE: self.energy_joules,
        }[metric]
        return self.quality_score / denominator


@dataclass(frozen=True, slots=True)
class EfficiencyValue:
    expert_id: str
    value: float


@dataclass(frozen=True, slots=True)
class EfficiencySelection:
    metric: EfficiencyMetric
    selected_expert_id: str
    values: tuple[EfficiencyValue, ...]


@dataclass(frozen=True, slots=True)
class ExpertEfficiencyReport:
    report_id: str
    meter_id: str
    benchmark_id: str
    measurements: tuple[ExpertEfficiencyMeasurement, ...]
    selections: tuple[EfficiencySelection, ...]
    contract_version: str = EFFICIENCY_REPORT_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if len(self.measurements) < 2 or len(self.selections) != len(EfficiencyMetric):
            raise ValueError("efficiency report requires comparison and all metrics")
        expected = tuple(_selection(metric, self.measurements) for metric in EfficiencyMetric)
        if self.selections != expected:
            raise ValueError("efficiency selections must derive from measurements")


def build_efficiency_report(report_id, meter_id, benchmark_id, measurements):
    values = tuple(measurements)
    return ExpertEfficiencyReport(
        report_id, meter_id, benchmark_id, values,
        tuple(_selection(metric, values) for metric in EfficiencyMetric),
    )


def _selection(metric, measurements):
    values = tuple(EfficiencyValue(item.expert_id, item.value(metric)) for item in measurements)
    selected = max(values, key=lambda item: (item.value, item.expert_id)).expert_id
    return EfficiencySelection(metric, selected, values)
