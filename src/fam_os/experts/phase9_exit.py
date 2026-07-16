"""Phase 9 capability-hierarchy exit-gate evidence."""

from dataclasses import dataclass

PHASE9_EXIT_CONTRACT_VERSION = "fam.expert.phase9-exit/v1alpha1"


@dataclass(frozen=True, slots=True)
class Phase9ExitEvidence:
    evidence_id: str
    mixed_benchmark_passed: bool
    total_tasks: int
    tasks_stopped_before_largest_tier: int
    largest_tier_task_ids: tuple[str, ...]
    phase_artifact_ids: tuple[str, ...]
    passed: bool
    contract_version: str = PHASE9_EXIT_CONTRACT_VERSION

    def __post_init__(self) -> None:
        majority = self.tasks_stopped_before_largest_tier > self.total_tasks / 2
        complete = len(self.phase_artifact_ids) == 8
        if self.passed != (self.mixed_benchmark_passed and majority and complete):
            raise ValueError("Phase 9 exit must derive from benchmark and all steps")
