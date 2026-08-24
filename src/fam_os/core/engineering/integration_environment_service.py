"""Core admission and lifecycle for bounded integration environments."""

from collections.abc import Callable
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
import base64
import hashlib
from uuid import uuid4

from fam_os.core.engineering.authority import EngineeringAuthority
from fam_os.core.engineering.database_service import EngineeringDecisionAuthorizer
from fam_os.core.engineering.grants import EngineeringAuthorizationRequest
from fam_os.core.engineering.integration_environment import (
    IntegrationEnvironmentPlan,
    IntegrationExecutionPermit,
    integration_environment_plan_digest,
)
from fam_os.core.engineering.integration_network import (
    IntegrationNetworkAttachmentKind,
    IntegrationNetworkEnforcementRequest,
)
from fam_os.core.engineering.integration_environment import (
    IntegrationNetworkMode, IntegrationServiceKind,
)
from fam_os.core.engineering.integration_environment_ports import (
    IntegrationEnvironmentExecutor,
)
from fam_os.core.engineering.integration_environment_receipts import (
    IntegrationEnvironmentReceipt,
    IntegrationEnvironmentStartResult,
)
from fam_os.core.engineering.integration_network import (
    validate_integration_network_usage,
)
from fam_os.core.engineering.transactions import CandidateWorkspace


class IntegrationEnvironmentService:
    def __init__(
        self,
        authorizer: EngineeringDecisionAuthorizer,
        executor: IntegrationEnvironmentExecutor,
        clock: Callable[[], datetime] | None = None,
        identifier: Callable[[], str] | None = None,
        network_authority=None,
    ) -> None:
        self._authorizer = authorizer
        self._executor = executor
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._identifier = identifier or (lambda: str(uuid4()))
        self._network_authority = network_authority

    def start(
        self,
        plan: IntegrationEnvironmentPlan,
        candidate: CandidateWorkspace,
        grant_id: str,
        principal_id: str,
        session_id: str,
        cancelled: Callable[[], bool],
        permit_observer: Callable[[IntegrationExecutionPermit], None] | None = None,
    ) -> IntegrationEnvironmentStartResult:
        self._validate_candidate(plan, candidate)
        now = self._clock()
        if not plan.created_at <= now < plan.expires_at:
            raise PermissionError("integration environment plan is not active")
        if cancelled():
            raise PermissionError("integration environment was cancelled")
        requests = self._requests(
            plan, candidate, grant_id, principal_id, session_id,
        )
        decisions = tuple(self._authorize(request) for request in requests)
        permit = IntegrationExecutionPermit(
            self._identifier(), plan.environment_id, plan.approved_changeset_id,
            plan.exact_host_id, tuple(item.decision_id for item in decisions),
            now, now + timedelta(minutes=5),
        )
        if plan.network_mode is IntegrationNetworkMode.ALLOWLIST:
            permit = replace(
                permit, network_request=self._network_request(
                    plan, permit, principal_id, session_id, requests, decisions,
                ),
            )
        if permit_observer is not None:
            permit_observer(permit)
        receipt = self._executor.launch(
            plan, Path(candidate.candidate_workspace), permit,
            _LiveIntegrationControl(self._authorizer, requests, cancelled),
        )
        if (
            receipt.environment_id != plan.environment_id
            or receipt.permit_id != permit.permit_id
        ):
            raise RuntimeError("integration executor returned mismatched evidence")
        self._validate_network_evidence(plan, receipt, require_finalized=False)
        return IntegrationEnvironmentStartResult(
            plan.environment_id, integration_environment_plan_digest(plan),
            permit, receipt,
        )

    def _network_request(
        self, plan, permit, principal_id, session_id, requests, decisions,
    ):
        if self._network_authority is None:
            raise PermissionError("integration network signing is unavailable")
        network_ids = tuple(
            decision.decision_id for request, decision in zip(requests, decisions)
            if request.authority is EngineeringAuthority.NETWORK
        )
        if len(network_ids) != len(plan.network_hosts):
            raise PermissionError("integration network decisions are incomplete")
        authority_ref = "network-authority-" + hashlib.sha256(
            "\0".join(network_ids).encode(),
        ).hexdigest()
        kinds = []
        if any(item.kind in {
            IntegrationServiceKind.PROCESS, IntegrationServiceKind.API,
            IntegrationServiceKind.BROWSER,
        } for item in plan.services):
            kinds.append(IntegrationNetworkAttachmentKind.LINUX_NAMESPACE)
        if any(item.kind in {
            IntegrationServiceKind.CONTAINER,
            IntegrationServiceKind.CLUSTER_CONTROL_PLANE,
        } for item in plan.services):
            kinds.append(IntegrationNetworkAttachmentKind.DOCKER_INTERNAL_NETWORK)
        draft = IntegrationNetworkEnforcementRequest(
            "network-request-" + permit.permit_id, plan.environment_id,
            permit.permit_id, plan.exact_host_id, principal_id, session_id,
            authority_ref, self._network_authority.key_id,
            base64.b64encode(bytes(64)).decode("ascii"),
            integration_environment_plan_digest(plan), tuple(kinds),
            plan.network_hosts, plan.resource_impact.max_network_bytes,
            min(plan.expires_at, permit.expires_at),
        )
        signed = self._network_authority.sign(draft)
        if signed != replace(draft, signature_base64=signed.signature_base64):
            raise PermissionError("integration network signer changed request scope")
        return signed

    def cleanup(
        self,
        plan: IntegrationEnvironmentPlan,
        candidate: CandidateWorkspace,
        receipt: IntegrationEnvironmentReceipt,
        permit: IntegrationExecutionPermit,
    ) -> IntegrationEnvironmentReceipt:
        self._validate_candidate(plan, candidate)
        if (
            permit.environment_id != plan.environment_id
            or permit.approved_changeset_id != plan.approved_changeset_id
            or permit.exact_host_id != plan.exact_host_id
            or receipt.environment_id != plan.environment_id
            or receipt.permit_id != permit.permit_id
        ):
            raise PermissionError("integration cleanup identities do not match")
        cleaned = self._executor.cleanup(
            plan, receipt, Path(candidate.candidate_workspace), permit,
        )
        self._validate_network_evidence(plan, cleaned, require_finalized=True)
        return cleaned

    @staticmethod
    def _validate_network_evidence(plan, receipt, *, require_finalized):
        if plan.network_mode.value == "allowlist":
            validate_integration_network_usage(
                plan, receipt.network_usage, require_finalized=require_finalized,
            )
        elif receipt.network_usage is not None:
            raise ValueError("non-allowlisted integration cannot claim network usage")

    def _requests(self, plan, candidate, grant_id, principal_id, session_id):
        values = [self._request(
            plan, candidate, grant_id, principal_id, session_id,
            EngineeringAuthority.EXECUTE, toolchain="integration-environment",
        )]
        values.extend(
            self._request(
                plan, candidate, grant_id, principal_id, session_id,
                EngineeringAuthority.NETWORK, network_host=host,
            )
            for host in plan.network_hosts
        )
        secret_refs = sorted({
            value for service in plan.services for value in service.secret_refs
        })
        values.extend(
            self._request(
                plan, candidate, grant_id, principal_id, session_id,
                EngineeringAuthority.SECRET_USE, secret_ref=secret_ref,
            )
            for secret_ref in secret_refs
        )
        return tuple(values)

    def _request(
        self, plan, candidate, grant_id, principal_id, session_id, authority,
        *, toolchain=None, network_host=None, secret_ref=None,
    ):
        return EngineeringAuthorizationRequest(
            self._identifier(), grant_id, principal_id, authority,
            plan.task_id, session_id, None, plan.approved_changeset_id,
            candidate.owner_workspace, None, toolchain, network_host,
            None, None, None, secret_ref, plan.resource_impact,
        )

    def _authorize(self, request):
        decision = self._authorizer.authorize(request)
        if (
            not decision.allowed
            or decision.request_id != request.request_id
            or decision.grant_id != request.grant_id
            or decision.authority is not request.authority
        ):
            raise PermissionError("integration environment lacks exact live authority")
        return decision

    @staticmethod
    def _validate_candidate(plan, candidate) -> None:
        if (
            plan.task_id != candidate.task_id
            or plan.candidate_id != candidate.candidate_id
            or plan.candidate_root != candidate.candidate_workspace
        ):
            raise ValueError("integration plan does not match candidate workspace")
        if candidate.owner_workspace == candidate.candidate_workspace:
            raise ValueError("integration candidate workspace is not isolated")


class _LiveIntegrationControl:
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
