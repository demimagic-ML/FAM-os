"""Core live authority admission for isolated PostgreSQL verification."""

from collections.abc import Callable
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from fam_os.core.engineering.authority import EngineeringAuthority
from fam_os.core.engineering.database_service import EngineeringDecisionAuthorizer
from fam_os.core.engineering.grants import EngineeringAuthorizationRequest


class PostgreSQLVerificationExecutor(Protocol):
    def execute(
        self,
        plan,
        candidate_root: Path,
        environment_plan,
        environment_receipt,
        permit,
        control,
        authorization_decision_ids,
    ) -> object: ...


class PostgreSQLIntegrationVerificationService:
    """Join primary edit authority to separately granted service resources."""

    def __init__(
        self,
        authorizer: EngineeringDecisionAuthorizer,
        executor: PostgreSQLVerificationExecutor,
        identifier: Callable[[], str] | None = None,
    ) -> None:
        self._authorizer = authorizer
        self._executor = executor
        self._identifier = identifier or (lambda: str(uuid4()))

    def execute(
        self,
        plan,
        candidate,
        environment_plan,
        environment_start,
        engineering_grant_id: str,
        integration_resource_grant_id: str,
        principal_id: str,
        session_id: str,
        cancelled: Callable[[], bool],
    ):
        self._validate(plan, candidate, environment_plan, environment_start)
        requests = self._requests(
            plan,
            candidate,
            environment_plan,
            engineering_grant_id,
            integration_resource_grant_id,
            principal_id,
            session_id,
        )
        decisions = tuple(self._authorize(request) for request in requests)
        control = _LivePostgreSQLControl(
            self._authorizer, requests, cancelled,
        )
        receipt = self._executor.execute(
            plan,
            Path(candidate.candidate_workspace),
            environment_plan,
            environment_start.receipt,
            environment_start.permit,
            control,
            tuple(item.decision_id for item in decisions),
        )
        if (
            not receipt.passed
            or receipt.plan_id != plan.plan_id
            or receipt.environment_id != plan.environment_id
            or receipt.permit_id != environment_start.permit.permit_id
            or receipt.authorization_decision_ids
            != tuple(item.decision_id for item in decisions)
        ):
            raise RuntimeError("PostgreSQL executor returned mismatched evidence")
        return receipt

    def _requests(
        self,
        plan,
        candidate,
        environment_plan,
        engineering_grant_id,
        resource_grant_id,
        principal_id,
        session_id,
    ):
        primary = [self._request(
            plan,
            candidate,
            engineering_grant_id,
            principal_id,
            session_id,
            EngineeringAuthority.EXECUTE,
            plan.execution_resource_impact,
            toolchain="sql",
        )]
        for asset in plan.migration_assets:
            for path in (asset.forward_path, asset.rollback_path):
                primary.append(self._request(
                    plan,
                    candidate,
                    engineering_grant_id,
                    principal_id,
                    session_id,
                    EngineeringAuthority.MODIFY,
                    plan.execution_resource_impact,
                    path=path,
                ))
        resources = (
            self._request(
                plan,
                candidate,
                resource_grant_id,
                principal_id,
                session_id,
                EngineeringAuthority.EXECUTE,
                environment_plan.resource_impact,
                toolchain="integration-environment",
            ),
            self._request(
                plan,
                candidate,
                resource_grant_id,
                principal_id,
                session_id,
                EngineeringAuthority.SECRET_USE,
                environment_plan.resource_impact,
                secret_ref=plan.connection_secret_ref,
            ),
        )
        return (*primary, *resources)

    def _request(
        self,
        plan,
        candidate,
        grant_id,
        principal_id,
        session_id,
        authority,
        impact,
        *,
        path=None,
        toolchain=None,
        secret_ref=None,
    ):
        return EngineeringAuthorizationRequest(
            self._identifier(), grant_id, principal_id, authority,
            plan.task_id, session_id, plan.plan_id,
            plan.approved_changeset_id, candidate.owner_workspace,
            path, toolchain, None, None, None, None, secret_ref, impact,
        )

    def _authorize(self, request):
        decision = self._authorizer.authorize(request)
        if (
            not decision.allowed
            or decision.request_id != request.request_id
            or decision.grant_id != request.grant_id
            or decision.authority is not request.authority
        ):
            raise PermissionError("PostgreSQL verification lacks exact live authority")
        return decision

    @staticmethod
    def _validate(plan, candidate, environment, start) -> None:
        if (
            plan.task_id != candidate.task_id
            or plan.candidate_id != candidate.candidate_id
            or environment.environment_id != plan.environment_id
            or environment.candidate_root != candidate.candidate_workspace
            or start.environment_id != plan.environment_id
            or start.permit.environment_id != plan.environment_id
            or start.receipt.environment_id != plan.environment_id
            or candidate.owner_workspace == candidate.candidate_workspace
        ):
            raise ValueError("PostgreSQL verification lifecycle identities differ")


class _LivePostgreSQLControl:
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
