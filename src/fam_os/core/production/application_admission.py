"""Admission and durable startup of capability-driven application requests."""

from datetime import datetime, timedelta, timezone

from fam_os.applications import (
    ApplicationAuthority,
    CapabilityKind,
    PermissionGrant,
    PermissionScope,
)
from fam_os.core.admission import RequestAdmissionService, RequestAuthorityGrant, RequestIdentity
from fam_os.core.contracts import TaskRequest
from fam_os.core.lifecycle import PlanLifecycleService
from fam_os.core.lifecycle import CandidateEvidenceRecord
from fam_os.core.production.application_contracts import (
    ApplicationExecutionRecord,
    ApplicationExecutionState,
)
from fam_os.core.production.application_plan_compiler import ApplicationPlanCompiler
from fam_os.core.production.contracts import InferenceExecutionRecord, InferenceExecutionState
from fam_os.core.production.execution_state import internal_capability
from fam_os.core.routing import RoutedTaskRequest
from fam_os.routing import RouteDecision, RoutingResult
from fam_os.shell import ShellContextKind


class ApplicationRequestStarter:
    def __init__(self, repositories, applications, classifier) -> None:
        self._repositories = repositories
        self._applications = applications
        self._classifier = classifier

    def start(
        self, command, intent, selection, instance_id,
        reversal_source_session_id=None, seeded_candidate_content=None,
    ):
        application_instance_id, resource_uri = _targets(command)
        requested = set(command.required_capabilities)
        for context in command.contexts:
            requested.update(context.capability_ids)
        requested.add(internal_capability(intent))
        capabilities = tuple(sorted(requested))
        entries = tuple(
            self._require_entry(application_instance_id, capability)
            for capability in capabilities
            if not capability.startswith("core.intent.")
        )
        if not entries:
            raise ValueError("application request has no live application capability")
        request = TaskRequest(
            command.request_id, command.prompt, capabilities,
            command.verification_required,
        )
        if not self._repositories.requests.add(request, "running"):
            raise ValueError("request already exists")
        routed = self._route(request, intent)
        plan = ApplicationPlanCompiler().compile(
            request.request_id, routed.routing.decision, entries,
            command.verification_required,
            deterministic_parameters=seeded_candidate_content is not None,
        )
        started = PlanLifecycleService(
            self._repositories.plans, instance_id_factory=lambda: instance_id,
        ).start(routed, plan)
        if started.rejection is not None:
            raise RuntimeError("application plan could not start")
        grant = _permission(request, entries, application_instance_id, resource_uri)
        self._repositories.application_permissions.put(grant)
        application = ApplicationExecutionRecord(
            instance_id, request.request_id, routed, application_instance_id,
            resource_uri, grant.grant_id, ApplicationExecutionState.ACTIVE, 0,
            reversal_source_session_id=reversal_source_session_id,
        )
        if not self._repositories.application_executions.create(application):
            raise RuntimeError("application execution could not be recorded")
        candidate_id = None
        state = InferenceExecutionState.PREPARED
        if seeded_candidate_content is not None:
            candidate_id = f"candidate-{request.request_id}-action-parameters"
            candidate = CandidateEvidenceRecord(
                candidate_id, request.request_id, plan.plan_id,
                seeded_candidate_content,
            )
            if not self._repositories.final_evidence.add_candidate(candidate):
                raise RuntimeError("deterministic action parameters already exist")
            state = InferenceExecutionState.CANDIDATE_READY
        inference = InferenceExecutionRecord(
            instance_id, request.request_id, intent, selection,
            state, 0, candidate_id=candidate_id,
        )
        if not self._repositories.inference_executions.create(inference):
            raise RuntimeError("application inference could not be recorded")
        return started.snapshot

    def _route(self, request, intent):
        now = datetime.now(timezone.utc)
        authority_ref = f"authority-{request.request_id}"
        session_id = f"shell-{request.request_id}"
        grant = RequestAuthorityGrant(
            authority_ref, "local-owner", session_id,
            request.required_capabilities, now - timedelta(seconds=1),
            now + timedelta(hours=1),
        )
        if not self._repositories.authorities.add(grant):
            raise ValueError("request authority already exists")
        admitted = RequestAdmissionService(
            self._repositories.authorities, self._repositories.request_replay,
        ).admit(request, RequestIdentity("local-owner", session_id, authority_ref))
        if not admitted.accepted:
            raise RuntimeError("application request admission failed")
        decision = RouteDecision(
            self._classifier.route(intent), 1.0,
            "Core policy classified a capability-driven application request.",
            request.required_capabilities,
        )
        return RoutedTaskRequest(admitted.admitted, RoutingResult(decision))

    def _require_entry(self, instance_id, capability_id):
        entry = self._applications.provider.capability(instance_id, capability_id)
        if entry is None:
            raise ValueError(f"application capability is unavailable: {capability_id}")
        return entry


def _targets(command):
    applications = tuple(
        item for item in command.contexts
        if item.kind is ShellContextKind.APPLICATION
    )
    if len(applications) != 1:
        raise ValueError("application requests require one application context")
    resources = tuple(
        item.resource_ref for item in command.contexts
        if item.kind in {ShellContextKind.FILE, ShellContextKind.URI, ShellContextKind.SELECTION}
    )
    if len(resources) > 1:
        raise ValueError("application requests require at most one resource context")
    return applications[0].resource_ref, resources[0] if resources else None


def _permission(request, entries, instance_id, resource_uri):
    authorities = {ApplicationAuthority.OBSERVE}
    for entry in entries:
        authorities.add(entry.capability.required_authority)
        if entry.capability.kind is CapabilityKind.ACTION:
            authorities.add(ApplicationAuthority.PROPOSE)
    now = datetime.now(timezone.utc)
    return PermissionGrant(
        f"grant-{request.request_id}", "local-owner",
        tuple(sorted(authorities, key=lambda item: item.value)),
        PermissionScope(
            application_ids=tuple(sorted({item.application_id for item in entries})),
            instance_ids=(instance_id,),
            capability_ids=tuple(sorted(item.capability_id for item in entries)),
            resource_uris=() if resource_uri is None else (resource_uri,),
        ),
        now - timedelta(seconds=1), now + timedelta(hours=1),
    )
