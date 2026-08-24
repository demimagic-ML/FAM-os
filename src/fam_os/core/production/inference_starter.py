"""Atomic ordering for durable production inference admission and plan start."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fam_os.core.admission import (
    RequestAdmissionService,
    RequestAuthorityGrant,
    RequestIdentity,
)
from fam_os.core.contracts import TaskRequest
from fam_os.core.ingress.shell_views import accepted_shell_snapshot
from fam_os.core.lifecycle import PlanLifecycleService
from fam_os.core.production.contracts import (
    InferenceExecutionRecord,
    InferenceExecutionState,
    RuntimeModelSelection,
)
from fam_os.core.production.execution_state import internal_capability
from fam_os.core.production.policy_router import PolicyIntentRouter
from fam_os.core.routing import CoreRoutingService


class InferenceRequestStarter:
    def __init__(
        self, repositories, selector, capacity, resident_models,
        plan_compiler, budget_factory, remote_planner=None,
    ) -> None:
        self._repositories = repositories
        self._selector = selector
        self._capacity = capacity
        self._resident_models = resident_models
        self._compiler = plan_compiler
        self._budget = budget_factory
        self._remote_planner = remote_planner

    def bind_remote_planner(self, planner) -> None:
        if self._remote_planner is not None:
            raise RuntimeError("remote execution planner is already bound")
        self._remote_planner = planner

    def start(
        self, command, intent, principal_id: str, session_id: str,
        declaration=None,
    ):
        request = TaskRequest(
            command.request_id, command.prompt, (internal_capability(intent),),
            command.verification_required,
        )
        instance_id = f"task-{request.request_id}"
        remote_plan = self._remote_plan(
            command, instance_id, request, intent,
        )
        selection = (
            self._remote_selection(request, intent, remote_plan)
            if remote_plan is not None else self._selector.select(
                request.request_id, intent, self._capacity(),
                resident_model_refs=self._resident_models(),
                required_verifier_id=(
                    None if declaration is None else declaration.contract.verifier_id
                ),
            )
        )
        declaration_added = self._add_declaration(declaration)
        if not self._repositories.requests.add(request, "running"):
            if declaration_added:
                self._repositories.verifications.remove_declaration(
                    declaration.declaration_id,
                )
            raise ValueError("request already exists")
        admission = RequestAdmissionService(
            self._repositories.authorities, self._repositories.request_replay,
        ).admit(request, self._authority(request, principal_id, session_id))
        if not admission.accepted or admission.admitted is None:
            raise RuntimeError("request admission failed")
        routed = CoreRoutingService(PolicyIntentRouter(intent)).route(admission.admitted)
        if not routed.succeeded or routed.routed is None:
            raise RuntimeError("request routing failed")
        plan = self._compiler.compile(
            request.request_id, routed.routed.routing.decision, intent,
            request.verification_required,
            declaration.contract.acceptance_id if declaration is not None else None,
        )
        started = PlanLifecycleService(
            self._repositories.plans, instance_id_factory=lambda: instance_id,
        ).start(routed.routed, plan)
        if started.rejection is not None:
            raise RuntimeError("request plan could not start")
        record = InferenceExecutionRecord(
            instance_id, request.request_id, intent, selection,
            InferenceExecutionState.PREPARED, 0, remote_plan=remote_plan,
        )
        if not self._repositories.inference_executions.create(record):
            raise RuntimeError("inference execution could not be recorded")
        self._budget(instance_id)
        return accepted_shell_snapshot(
            instance_id, request.request_id,
            f"Accepted as {intent.value}; selected {selection.model_ref}",
        )

    def _remote_selection(self, request, intent, plan):
        capacity = self._capacity()
        return RuntimeModelSelection(
            f"selection-{plan.plan_id}", request.request_id, intent,
            plan.model_ref, plan.expert_tier, 0, capacity.available_host_bytes,
            capacity.available_vram_bytes,
            (*plan.reason_codes, "fabric.route.remote"),
        )

    def _remote_plan(self, command, instance_id, request, intent):
        authority = command.remote_authority
        if authority is None:
            return None
        if self._remote_planner is None:
            raise PermissionError("remote execution is unavailable")
        return self._remote_planner.plan(
            instance_id, request.request_id, intent, authority,
            verification_required=request.verification_required,
        )

    def _add_declaration(self, declaration) -> bool:
        if declaration is None:
            return False
        if not self._repositories.verifications.add_declaration(declaration):
            raise ValueError("verification declaration already exists")
        return True

    def _authority(
        self, request: TaskRequest, principal_id: str, session_id: str,
    ) -> RequestIdentity:
        now = datetime.now(timezone.utc)
        authority_ref = f"authority-{request.request_id}"
        grant = RequestAuthorityGrant(
            authority_ref, principal_id, session_id, request.required_capabilities,
            now - timedelta(seconds=1), now + timedelta(hours=1),
        )
        if not self._repositories.authorities.add(grant):
            raise ValueError("request authority already exists")
        return RequestIdentity(principal_id, session_id, authority_ref)
