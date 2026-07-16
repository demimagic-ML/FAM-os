"""Local expert-frequency learning from auditable verified outcomes."""

from dataclasses import dataclass
from datetime import datetime

EXPERT_FREQUENCY_CONTRACT_VERSION = "fam.scheduler.expert-frequency/v1alpha1"


@dataclass(frozen=True, slots=True)
class ExpertUseObservation:
    observation_id: str
    expert_id: str
    observed_at: datetime
    verified: bool


@dataclass(frozen=True, slots=True)
class ExpertFrequency:
    expert_id: str
    verified_uses: int
    total_uses: int
    frequency: float


@dataclass(frozen=True, slots=True)
class ExpertFrequencyProfile:
    profile_id: str
    observations: int
    frequencies: tuple[ExpertFrequency, ...]
    local_only: bool = True
    contract_version: str = EXPERT_FREQUENCY_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if not self.local_only or self.observations != sum(item.total_uses for item in self.frequencies):
            raise ValueError("expert frequency profile must derive from local observations")


class LocalExpertFrequencyLearner:
    def learn(self, profile_id, observations) -> ExpertFrequencyProfile:
        values = tuple(observations)
        counts: dict[str, list[int]] = {}
        for item in values:
            if item.observed_at.tzinfo is None:
                raise ValueError("expert use observation time must be timezone-aware")
            count = counts.setdefault(item.expert_id, [0, 0])
            count[1] += 1
            count[0] += int(item.verified)
        frequencies = tuple(
            ExpertFrequency(expert, verified, total, total / len(values))
            for expert, (verified, total) in sorted(counts.items())
        )
        return ExpertFrequencyProfile(profile_id, len(values), frequencies)
