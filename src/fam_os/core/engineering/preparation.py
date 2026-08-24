"""Active bounded preparation from durable intent to isolated candidate."""

from dataclasses import dataclass
from typing import Protocol

from fam_os.core.engineering.lifecycle_driver import EngineeringLifecycleDriver
from fam_os.core.engineering.repository import (
    ArchitectureProposal, BoundedRepositoryPlanner, RepositoryAnalysis,
    RepositoryAnalysisRequest, RepositoryEvidenceBundle,
)
from fam_os.core.engineering.task_definition import EngineeringTaskDefinition
from fam_os.core.engineering.transactions import CandidateWorkspace
from fam_os.core.engineering.version import ENGINEERING_CONTRACT_VERSION
from fam_os.core.engineering._validation import text


class RepositoryEvidenceObserver(Protocol):
    def observe(self, task_id: str, workspace_root: str) -> RepositoryEvidenceBundle: ...


class CandidateWorkspaceFactory(Protocol):
    def create(self, task_id: str) -> CandidateWorkspace: ...


class EngineeringPreparationStore(Protocol):
    def put(self, result: "EngineeringPreparationResult") -> None: ...
    def load(self, task_id: str) -> "EngineeringPreparationResult | None": ...
    def load_pending(self, task_id: str) -> "EngineeringPreparationResult | None": ...
    def mark_committed(self, task_id: str, definition_id: str) -> None: ...


@dataclass(frozen=True, slots=True)
class EngineeringPreparationResult:
    definition_id: str
    evidence: RepositoryEvidenceBundle
    analysis: RepositoryAnalysis
    proposal: ArchitectureProposal
    candidate: CandidateWorkspace
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        text(self.definition_id, "definition_id")
        if (
            self.evidence.task_id != self.analysis.task_id
            or self.analysis.task_id != self.proposal.task_id
            or self.proposal.task_id != self.candidate.task_id
            or self.analysis.bundle_id != self.evidence.bundle_id
            or self.proposal.analysis_id != self.analysis.analysis_id
        ):
            raise ValueError("engineering preparation result identities are mismatched")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("engineering preparation result version is unsupported")


class EngineeringPreparationOrchestrator:
    def __init__(
        self,
        observer: RepositoryEvidenceObserver,
        planner: BoundedRepositoryPlanner,
        candidates: CandidateWorkspaceFactory,
        lifecycle: EngineeringLifecycleDriver,
        records: EngineeringPreparationStore,
    ) -> None:
        self._observer = observer
        self._planner = planner
        self._candidates = candidates
        self._lifecycle = lifecycle
        self._records = records

    def prepare(
        self,
        definition: EngineeringTaskDefinition,
        request: RepositoryAnalysisRequest,
    ) -> EngineeringPreparationResult:
        task = definition.task
        if request.task_id != task.task_id or request.query != task.intent:
            raise ValueError("repository analysis request differs from durable task intent")
        if len(task.workspace_roots) != 1:
            raise ValueError("single-repository preparation requires one workspace root")
        pending = self._records.load_pending(task.task_id)
        if pending is not None:
            _validate_pending(pending, definition, request)
            if not self._lifecycle.preparation_is_recorded(
                pending.analysis, pending.proposal, pending.candidate,
            ):
                self._lifecycle.record_preparation(
                    pending.analysis, pending.proposal, pending.candidate,
                )
            self._records.mark_committed(task.task_id, definition.definition_id)
            return pending
        evidence = self._observer.observe(task.task_id, task.workspace_roots[0])
        if evidence.task_id != task.task_id or evidence.workspace_root != task.workspace_roots[0]:
            raise ValueError("repository observation differs from durable task scope")
        analysis = self._planner.analyze(
            request, evidence, completed_at=evidence.captured_at,
        )
        proposal = self._planner.propose(
            request, analysis, evidence, created_at=evidence.captured_at,
        )
        candidate = self._candidates.create(task.task_id)
        if candidate.owner_workspace != task.workspace_roots[0]:
            raise ValueError("candidate factory used a different owner workspace")
        result = EngineeringPreparationResult(
            definition.definition_id, evidence, analysis, proposal, candidate,
        )
        self._records.put(result)
        self._lifecycle.record_preparation(analysis, proposal, candidate)
        self._records.mark_committed(task.task_id, definition.definition_id)
        return result


def _validate_pending(
    result: EngineeringPreparationResult,
    definition: EngineeringTaskDefinition,
    request: RepositoryAnalysisRequest,
) -> None:
    task = definition.task
    if (
        result.definition_id != definition.definition_id
        or result.candidate.task_id != task.task_id
        or result.candidate.owner_workspace != task.workspace_roots[0]
        or result.analysis.request_id != request.request_id
        or result.analysis.task_id != request.task_id
    ):
        raise RuntimeError("pending engineering preparation differs from durable intent")
