"""Explicit empirical sample plans for Phase 22 learning-curve checkpoints."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PartitionQuotas:
    train: int
    validation: int
    held_out: int

    def __post_init__(self) -> None:
        if min(self.train, self.validation, self.held_out) < 1:
            raise ValueError("sample-plan partition quotas must be positive")

    def tuple(self) -> tuple[int, int, int]:
        return self.train, self.validation, self.held_out


@dataclass(frozen=True, slots=True)
class SpecialistSamplePlan:
    plan_id: str
    quality: PartitionQuotas
    safety: PartitionQuotas
    policy: PartitionQuotas
    unrelated: PartitionQuotas

    def __post_init__(self) -> None:
        if not self.plan_id.strip():
            raise ValueError("sample-plan identity is invalid")

    def quotas(self, kind: str) -> tuple[int, int, int]:
        values = {
            "quality": self.quality,
            "safety": self.safety,
            "policy": self.policy,
            "unrelated": self.unrelated,
        }
        try:
            return values[kind].tuple()
        except KeyError as error:
            raise ValueError("sample-plan fixture kind is invalid") from error

    @property
    def training_examples(self) -> int:
        return sum(
            value.train for value in (
                self.quality, self.safety, self.policy, self.unrelated,
            )
        )

    @property
    def total_examples(self) -> int:
        return sum(
            sum(value.tuple()) for value in (
                self.quality, self.safety, self.policy, self.unrelated,
            )
        )


QUALITY256 = SpecialistSamplePlan(
    "quality256",
    quality=PartitionQuotas(256, 32, 32),
    safety=PartitionQuotas(16, 2, 2),
    policy=PartitionQuotas(16, 2, 2),
    unrelated=PartitionQuotas(16, 2, 2),
)

BALANCED512 = SpecialistSamplePlan(
    "balanced512",
    quality=PartitionQuotas(256, 32, 32),
    safety=PartitionQuotas(96, 12, 8),
    policy=PartitionQuotas(96, 12, 8),
    unrelated=PartitionQuotas(64, 8, 8),
)

BALANCED1000 = SpecialistSamplePlan(
    "balanced1000",
    quality=PartitionQuotas(400, 50, 32),
    safety=PartitionQuotas(120, 15, 8),
    policy=PartitionQuotas(360, 45, 8),
    unrelated=PartitionQuotas(120, 15, 8),
)

BALANCED2500 = SpecialistSamplePlan(
    "balanced2500",
    quality=PartitionQuotas(1250, 156, 32),
    safety=PartitionQuotas(375, 47, 8),
    policy=PartitionQuotas(500, 63, 8),
    unrelated=PartitionQuotas(375, 46, 8),
)

BALANCED5000 = SpecialistSamplePlan(
    "balanced5000",
    quality=PartitionQuotas(2500, 312, 32),
    safety=PartitionQuotas(1000, 125, 8),
    policy=PartitionQuotas(1000, 125, 8),
    unrelated=PartitionQuotas(500, 63, 8),
)

DIVERSE2500 = SpecialistSamplePlan(
    "diverse2500",
    quality=PartitionQuotas(1250, 156, 32),
    safety=PartitionQuotas(500, 63, 8),
    policy=PartitionQuotas(500, 63, 8),
    unrelated=PartitionQuotas(250, 30, 8),
)

SAMPLE_PLANS = {
    item.plan_id: item for item in (
        QUALITY256, BALANCED512, BALANCED1000, BALANCED2500, BALANCED5000,
        DIVERSE2500,
    )
}
SAMPLE_PLAN_IDS = tuple(sorted(SAMPLE_PLANS))


def sample_plan(plan_id: str) -> SpecialistSamplePlan:
    try:
        return SAMPLE_PLANS[plan_id]
    except KeyError as error:
        raise ValueError(f"unknown specialist sample plan: {plan_id}") from error
