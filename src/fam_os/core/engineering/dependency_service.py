"""Core orchestration for approved isolated dependency resolution."""

from datetime import datetime
from typing import Protocol

from fam_os.core.engineering.authority import EngineeringTaskEnvelope
from fam_os.core.engineering.dependencies import (
    DependencyResolutionReceipt, DependencyResolutionRequest,
)
from fam_os.core.engineering.dependency_policy import DependencyAdmissionPolicy
from fam_os.core.engineering.grants import EngineeringAuthorityGrant
from fam_os.core.engineering.transactions import CandidateWorkspace


class IsolatedDependencyResolver(Protocol):
    def resolve(
        self,
        request: DependencyResolutionRequest,
        candidate: CandidateWorkspace,
    ) -> DependencyResolutionReceipt: ...


class EngineeringDependencyService:
    def __init__(
        self,
        policy: DependencyAdmissionPolicy,
        resolver: IsolatedDependencyResolver,
    ) -> None:
        self._policy = policy
        self._resolver = resolver

    def resolve(
        self,
        request: DependencyResolutionRequest,
        task: EngineeringTaskEnvelope,
        grant: EngineeringAuthorityGrant,
        candidate: CandidateWorkspace,
        *,
        instant: datetime,
    ) -> DependencyResolutionReceipt:
        if request.candidate_id != candidate.candidate_id:
            raise PermissionError("dependency request targets a different candidate")
        if candidate.task_id != task.task_id:
            raise PermissionError("candidate and dependency task are mismatched")
        self._policy.authorize(request, task, grant, instant=instant)
        receipt = self._resolver.resolve(request, candidate)
        self._policy.validate_receipt(request, receipt)
        return receipt
