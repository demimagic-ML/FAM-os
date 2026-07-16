"""Evidence-based expert split, merge, and retirement proposals."""

from dataclasses import dataclass
from enum import StrEnum

EXPERT_EVOLUTION_CONTRACT_VERSION = "fam.expert.evolution/v1alpha1"


class EvolutionAction(StrEnum):
    SPLIT = "split"
    MERGE = "merge"
    RETIRE = "retire"


@dataclass(frozen=True, slots=True)
class ExpertPerformanceSlice:
    expert_id: str
    capability_id: str
    task_cluster: str
    passed_cases: int
    total_cases: int
    quality_per_joule: float

    @property
    def quality(self) -> float:
        return self.passed_cases / self.total_cases


@dataclass(frozen=True, slots=True)
class ExpertEvolutionProposal:
    proposal_id: str
    action: EvolutionAction
    subject_expert_ids: tuple[str, ...]
    evidence_slice_ids: tuple[str, ...]
    reason_codes: tuple[str, ...]
    approval_required: bool = True
    state_mutated: bool = False
    contract_version: str = EXPERT_EVOLUTION_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if not self.approval_required or self.state_mutated:
            raise ValueError("evolution evidence cannot mutate expert state")
        if not self.subject_expert_ids or not self.evidence_slice_ids:
            raise ValueError("evolution proposal requires subjects and evidence")


@dataclass(frozen=True, slots=True)
class ExpertEvolutionReport:
    report_id: str
    source_benchmark_ids: tuple[str, ...]
    proposals: tuple[ExpertEvolutionProposal, ...]
    applied_proposal_ids: tuple[str, ...] = ()
    contract_version: str = EXPERT_EVOLUTION_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if not self.source_benchmark_ids or not self.proposals:
            raise ValueError("evolution report requires benchmarks and proposals")
        if self.applied_proposal_ids:
            raise ValueError("evolution report cannot apply proposals")


@dataclass(frozen=True, slots=True)
class ExpertEvolutionPolicy:
    minimum_cases: int = 20
    split_quality_gap: float = .25
    merge_quality_gap: float = .05
    retirement_quality_margin: float = .10

    def split(self, expert_id, slices) -> ExpertEvolutionProposal | None:
        eligible = tuple(item for item in slices if item.expert_id == expert_id and item.total_cases >= self.minimum_cases)
        if len(eligible) < 2:
            return None
        if max(item.quality for item in eligible) - min(item.quality for item in eligible) < self.split_quality_gap:
            return None
        return _proposal(EvolutionAction.SPLIT, (expert_id,), eligible, "cluster.quality-gap")

    def merge(self, left_id, right_id, slices) -> ExpertEvolutionProposal | None:
        pairs = _paired(left_id, right_id, slices, self.minimum_cases)
        if not pairs or any(abs(left.quality - right.quality) > self.merge_quality_gap for left, right in pairs):
            return None
        evidence = tuple(value for pair in pairs for value in pair)
        return _proposal(EvolutionAction.MERGE, (left_id, right_id), evidence, "experts.redundant-quality")

    def retire(self, subject_id, replacement_id, slices) -> ExpertEvolutionProposal | None:
        pairs = _paired(subject_id, replacement_id, slices, self.minimum_cases)
        if not pairs or any(
            replacement.quality < subject.quality + self.retirement_quality_margin
            or replacement.quality_per_joule < subject.quality_per_joule
            for subject, replacement in pairs
        ):
            return None
        evidence = tuple(value for pair in pairs for value in pair)
        return _proposal(EvolutionAction.RETIRE, (subject_id, replacement_id), evidence, "replacement.dominates")


def _paired(left_id, right_id, slices, minimum):
    left = {item.task_cluster: item for item in slices if item.expert_id == left_id and item.total_cases >= minimum}
    right = {item.task_cluster: item for item in slices if item.expert_id == right_id and item.total_cases >= minimum}
    return tuple((left[key], right[key]) for key in sorted(left.keys() & right.keys()))


def _proposal(action, subjects, evidence, reason):
    ids = tuple(f"{item.expert_id}:{item.task_cluster}" for item in evidence)
    return ExpertEvolutionProposal(f"proposal-{action.value}", action, subjects, ids, (reason,))
