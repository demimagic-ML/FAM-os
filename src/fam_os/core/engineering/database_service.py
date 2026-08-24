"""Core authority admission for candidate database execution."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from fam_os.core.engineering.authority import EngineeringAuthority
from fam_os.core.engineering.database import DatabaseChangePlan
from fam_os.core.engineering.database_ports import (
    DatabaseExecutionControl,
    DatabaseExecutionPermit,
)
from fam_os.core.engineering.grants import (
    EngineeringAuthorizationDecision,
    EngineeringAuthorizationRequest,
)
from fam_os.core.engineering.transactions import CandidateWorkspace


class EngineeringDecisionAuthorizer(Protocol):
    def authorize(
        self, request: EngineeringAuthorizationRequest,
    ) -> EngineeringAuthorizationDecision: ...


class CandidateDatabaseExecutor(Protocol):
    def execute(
        self,
        plan: DatabaseChangePlan,
        candidate_root: Path,
        permit: DatabaseExecutionPermit,
        control: DatabaseExecutionControl,
    ) -> object: ...


class CandidateDatabaseRecovery(Protocol):
    def reconcile(
        self,
        plan: DatabaseChangePlan,
        candidate_root: Path,
        permit: DatabaseExecutionPermit,
        control: DatabaseExecutionControl,
    ) -> object: ...


class DatabaseEngineeringService:
    def __init__(
        self,
        authorizer: EngineeringDecisionAuthorizer,
        executor: CandidateDatabaseExecutor,
        clock: Callable[[], datetime] | None = None,
        identifier: Callable[[], str] | None = None,
        *,
        recovery: CandidateDatabaseRecovery | None = None,
    ) -> None:
        self._authorizer = authorizer
        self._executor = executor
        self._recovery = recovery
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._identifier = identifier or (lambda: str(uuid4()))

    def execute(
        self,
        plan: DatabaseChangePlan,
        candidate: CandidateWorkspace,
        grant_id: str,
        principal_id: str,
        session_id: str,
        cancelled: Callable[[], bool],
    ) -> object:
        return self._run(
            plan, candidate, grant_id, principal_id, session_id, cancelled,
            self._executor.execute,
        )

    def reconcile(
        self,
        plan: DatabaseChangePlan,
        candidate: CandidateWorkspace,
        grant_id: str,
        principal_id: str,
        session_id: str,
        cancelled: Callable[[], bool],
    ) -> object:
        if self._recovery is None:
            raise RuntimeError("database recovery was not composed")
        return self._run(
            plan, candidate, grant_id, principal_id, session_id, cancelled,
            self._recovery.reconcile,
        )

    def _run(
        self, plan, candidate, grant_id, principal_id, session_id, cancelled,
        effect,
    ):
        self._validate_candidate(plan, candidate)
        requests = tuple(
            self._request(
                plan, candidate, grant_id, principal_id, session_id, authority,
            )
            for authority in (EngineeringAuthority.EXECUTE, EngineeringAuthority.MODIFY)
        )
        self._require_allowed(requests)
        now = self._clock()
        permit = DatabaseExecutionPermit(
            self._identifier(), plan.approved_changeset_id,
            plan.target.exact_host_id, now, now + timedelta(minutes=5),
        )
        control = _LiveDatabaseControl(
            self._authorizer, requests, cancelled,
        )
        return effect(
            plan, Path(candidate.candidate_workspace), permit, control,
        )

    def _request(
        self, plan, candidate, grant_id, principal_id, session_id, authority,
    ) -> EngineeringAuthorizationRequest:
        return EngineeringAuthorizationRequest(
            self._identifier(), grant_id, principal_id, authority,
            plan.task_id, session_id, None, plan.approved_changeset_id,
            candidate.owner_workspace, plan.target.database_name,
            None, None, None, None, None, None,
            plan.execution_resource_impact,
        )

    def _require_allowed(self, requests) -> None:
        for request in requests:
            decision = self._authorizer.authorize(request)
            if (
                not decision.allowed
                or decision.request_id != request.request_id
                or decision.grant_id != request.grant_id
                or decision.authority is not request.authority
            ):
                raise PermissionError("database execution lacks exact live authority")

    @staticmethod
    def _validate_candidate(plan, candidate) -> None:
        if plan.task_id != candidate.task_id or plan.candidate_id != candidate.candidate_id:
            raise ValueError("database plan does not match its candidate workspace")
        root = Path(candidate.candidate_workspace)
        if not root.is_absolute() or candidate.owner_workspace == candidate.candidate_workspace:
            raise ValueError("database candidate workspace is not isolated")


class _LiveDatabaseControl:
    def __init__(self, authorizer, requests, cancelled) -> None:
        self._authorizer = authorizer
        self._requests = requests
        self._cancelled = cancelled

    def cancelled(self) -> bool:
        return self._cancelled()

    def authorization_active(self) -> bool:
        for request in self._requests:
            decision = self._authorizer.authorize(request)
            if (
                not decision.allowed
                or decision.request_id != request.request_id
                or decision.grant_id != request.grant_id
                or decision.authority is not request.authority
            ):
                return False
        return True
