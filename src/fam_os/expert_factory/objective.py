"""Hardware-aware training objective with explicit movement and energy costs."""

from dataclasses import dataclass

FACTORY_OBJECTIVE_CONTRACT_VERSION = "fam.factory.hardware-objective/v1alpha1"


@dataclass(frozen=True, slots=True)
class HardwareTrainingMetrics:
    quality: float
    activated_parameters: int
    bytes_moved: int
    latency_seconds: float
    energy_joules: float


@dataclass(frozen=True, slots=True)
class HardwareObjectiveWeights:
    activated_parameters: float
    bytes_moved: float
    latency: float
    energy: float


def hardware_objective(metrics, weights):
    if not 0 <= metrics.quality <= 1:
        raise ValueError("training quality must be normalized")
    penalty = (metrics.activated_parameters * weights.activated_parameters +
               metrics.bytes_moved * weights.bytes_moved +
               metrics.latency_seconds * weights.latency +
               metrics.energy_joules * weights.energy)
    return metrics.quality - penalty
