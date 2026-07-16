import unittest
from datetime import datetime, timedelta, timezone

from fam_os.applications import (
    ActionProposal,
    ApplicationAuthority,
    ApplicationFailure,
    ApplicationFailureCategory,
    ApplicationRetryDisposition,
    CapabilityDescriptor,
    CapabilityKind,
    CapabilityRegistryEntry,
    ConditionRequirement,
    ConfirmationPolicy,
    ObservationResult,
    ObservationStatus,
    PermissionGrant,
    PermissionScope,
    Reversibility,
)
from fam_os.core.admission import AdmittedTaskRequest, RequestPermissionContext
from fam_os.core.contracts import (
    ExecutionPlan,
    PlanStep,
    PlanStepKind,
    PlanTransition,
    StepOutcome,
    TaskRequest,
    TerminalDisposition,
)
from fam_os.core.lifecycle import (
    ActionProposalAcquisition,
    ApplicationStepRejection,
    ApplicationStepService,
    InMemoryPlanStateRepository,
    ObservationAcquisition,
    PlanEvidenceKind,
    PlanLifecycleService,
    PlanRejection,
)
from fam_os.core.routing import RoutedTaskRequest
from fam_os.routing import RouteDecision, RouteName, RoutingResult


NOW = datetime(2026, 7, 16, 19, tzinfo=timezone.utc)
OBSERVE = "vscode.editor.active"
ACTION = "vscode.workspace_edit.apply"
RESOURCE = "file:///workspace/fam-os/app.py"


class PermissionRegistry:
    def __init__(self, grant):
        self.grant = grant

    def get(self, grant_id):
        return self.grant if self.grant and self.grant.grant_id == grant_id else None


class Provider:
    def __init__(self, entry, evidence=None, error=None):
        self.entry = entry
        self.evidence = evidence
        self.error = error
        self.observation_requests = []
        self.proposal_requests = []

    def capability(self, instance_id, capability_id):
        if self.entry.instance_id == instance_id and self.entry.capability_id == capability_id:
            return self.entry
        return None

    def observe(self, request):
        self.observation_requests.append(request)
        if self.error:
            raise self.error
        if self.evidence:
            return self.evidence(request)
        return ObservationResult(
            request.request_id, ObservationStatus.OBSERVED, NOW,
            {"language_id": "python", "text": "private source"}, RESOURCE, "7",
        )

    def prepare_action(self, request):
        self.proposal_requests.append(request)
        if self.error:
            raise self.error
        if self.evidence:
            return self.evidence(request)
        return proposal(request)


class CoreApplicationStepTests(unittest.TestCase):
    def test_observation_advances_with_reference_but_persists_no_payload(self):
        runtime, application, provider = setup(OBSERVE, ApplicationAuthority.OBSERVE)
        command = observation_command(runtime)

        result = application.acquire_observation(command)

        self.assertEqual(TerminalDisposition.RELEASE, result.snapshot.terminal_disposition)
        reference = result.snapshot.events[-1].evidence_refs[0]
        self.assertEqual(PlanEvidenceKind.OBSERVATION, reference.kind)
        self.assertEqual("evidence-1", reference.reference_id)
        self.assertEqual("private source", result.evidence.payload["text"])
        self.assertNotIn("private source", repr(result.snapshot))
        self.assertEqual(1, len(provider.observation_requests))

    def test_connector_denial_follows_declared_denied_edge(self):
        def denied(request):
            failure = ApplicationFailure(
                ApplicationFailureCategory.PERMISSION_DENIED,
                "application.permission.denied", "Permission was denied.",
                ApplicationRetryDisposition.AFTER_USER_ACTION,
            )
            return ObservationResult(
                request.request_id, ObservationStatus.DENIED, NOW, error=failure
            )

        runtime, application, _ = setup(
            OBSERVE, ApplicationAuthority.OBSERVE, evidence=denied
        )
        result = application.acquire_observation(observation_command(runtime))

        self.assertEqual(TerminalDisposition.WITHHOLD, result.snapshot.terminal_disposition)
        self.assertEqual(StepOutcome.DENIED, result.snapshot.events[-1].outcome)
        self.assertFalse(result.evidence.payload)

    def test_expired_core_and_application_permissions_stop_before_provider(self):
        for core_expired, app_expired in ((True, False), (False, True)):
            with self.subTest(core=core_expired, app=app_expired):
                runtime, application, provider = setup(
                    OBSERVE, ApplicationAuthority.OBSERVE,
                    core_expired=core_expired, app_expired=app_expired,
                )
                result = application.acquire_observation(observation_command(runtime))
                self.assertEqual(ApplicationStepRejection.PERMISSION_DENIED, result.rejection)
                self.assertEqual([], provider.observation_requests)

    def test_scope_and_subject_mismatch_stop_before_provider(self):
        for subject, resource in (("other-user", RESOURCE), ("principal-1", "file:///other")):
            with self.subTest(subject=subject, resource=resource):
                runtime, application, provider = setup(
                    OBSERVE, ApplicationAuthority.OBSERVE,
                    grant_subject=subject, grant_resource=resource,
                )
                result = application.acquire_observation(observation_command(runtime))
                self.assertEqual(ApplicationStepRejection.PERMISSION_DENIED, result.rejection)
                self.assertEqual([], provider.observation_requests)

    def test_wrong_step_and_route_context_never_reach_provider(self):
        runtime, application, provider = setup(OBSERVE, ApplicationAuthority.OBSERVE)
        wrong_command = action_command(runtime, routed_override=routed(ACTION))

        wrong_step = application.acquire_action_proposal(wrong_command)

        self.assertIn(
            wrong_step.rejection,
            (ApplicationStepRejection.INVALID_CONTEXT, ApplicationStepRejection.INVALID_STEP),
        )
        self.assertEqual([], provider.proposal_requests)

    def test_action_proposal_requires_propose_and_persists_only_reference(self):
        runtime, application, provider = setup(ACTION, ApplicationAuthority.PROPOSE)
        command = action_command(runtime)

        result = application.acquire_action_proposal(command)

        self.assertEqual("confirm-action", result.snapshot.current_step_id)
        self.assertIsNone(result.snapshot.terminal_disposition)
        reference = result.snapshot.events[-1].evidence_refs[0]
        self.assertEqual(PlanEvidenceKind.ACTION_PROPOSAL, reference.kind)
        self.assertEqual("proposal-1", reference.reference_id)
        self.assertEqual("-old\n+new", result.evidence.preview["diff"])
        self.assertNotIn("-old", repr(result.snapshot))
        self.assertEqual(1, len(provider.proposal_requests))

    def test_modify_authority_alone_cannot_prepare_action(self):
        runtime, application, provider = setup(ACTION, ApplicationAuthority.MODIFY)
        result = application.acquire_action_proposal(action_command(runtime))
        self.assertEqual(ApplicationStepRejection.PERMISSION_DENIED, result.rejection)
        self.assertEqual([], provider.proposal_requests)

    def test_forged_proposal_and_provider_exception_do_not_advance(self):
        def forged(request):
            wrong = request.__class__(
                "wrong-request", request.instance_id, request.capability_id,
                request.permission_grant_id, request.summary,
            )
            return proposal(wrong)

        for evidence, error, rejection in (
            (forged, None, ApplicationStepRejection.INVALID_EVIDENCE),
            (None, RuntimeError("secret /home/private"), ApplicationStepRejection.PROVIDER_UNAVAILABLE),
        ):
            with self.subTest(rejection=rejection):
                runtime, application, _ = setup(
                    ACTION, ApplicationAuthority.PROPOSE, evidence=evidence, error=error
                )
                started = runtime.repository.get("instance-1")
                result = application.acquire_action_proposal(action_command(runtime))
                self.assertEqual(rejection, result.rejection)
                self.assertEqual(started, runtime.repository.get("instance-1"))

    def test_stale_revision_is_rejected_before_application_access(self):
        runtime, application, provider = setup(OBSERVE, ApplicationAuthority.OBSERVE)
        command = observation_command(runtime, expected_revision=4)
        result = application.acquire_observation(command)
        self.assertEqual(PlanRejection.REVISION_CONFLICT, result.rejection)
        self.assertEqual([], provider.observation_requests)


def setup(
    capability_id, authority, evidence=None, error=None, core_expired=False,
    app_expired=False, grant_subject="principal-1", grant_resource=RESOURCE,
):
    routed_request = routed(capability_id, core_expired)
    lifecycle = lifecycle_service()
    lifecycle.start(routed_request, execution_plan(capability_id))
    entry = capability_entry(capability_id)
    provider = Provider(entry, evidence, error)
    grant = permission_grant(
        authority, capability_id, app_expired, grant_subject, grant_resource
    )
    application = ApplicationStepService(
        lifecycle, provider, PermissionRegistry(grant), clock=lambda: NOW,
        evidence_id_factory=lambda: "evidence-1",
    )
    return lifecycle, application, provider


def routed(capability_id, expired=False):
    valid_until = NOW if expired else NOW + timedelta(hours=1)
    request = TaskRequest("request-1", "Work in the editor", (capability_id,))
    permission = RequestPermissionContext(
        "principal-1", "session-1", "authority-1", (capability_id,), valid_until
    )
    admitted = AdmittedTaskRequest("admission-1", request, permission, NOW - timedelta(minutes=1))
    return RoutedTaskRequest(admitted, RoutingResult(route(capability_id)))


def route(capability_id):
    return RouteDecision(RouteName.CODE, 0.9, "Editor task.", (capability_id,))


def execution_plan(capability_id):
    kind = PlanStepKind.OBSERVE if capability_id == OBSERVE else PlanStepKind.PREPARE_ACTION
    steps = [
        PlanStep("application-step", kind, "Use application", (capability_id,)),
        terminal("release", TerminalDisposition.RELEASE),
        terminal("withhold", TerminalDisposition.WITHHOLD),
    ]
    transitions = [
        PlanTransition("application-step", StepOutcome.SUCCEEDED, "release"),
        PlanTransition("application-step", StepOutcome.DENIED, "withhold"),
        PlanTransition("application-step", StepOutcome.FAILED, "withhold"),
        PlanTransition("application-step", StepOutcome.UNAVAILABLE, "withhold"),
    ]
    if capability_id == ACTION:
        steps.insert(1, PlanStep(
            "confirm-action", PlanStepKind.CONFIRM_ACTION,
            "Wait for explicit confirmation", (capability_id,),
        ))
        transitions[0] = PlanTransition(
            "application-step", StepOutcome.SUCCEEDED, "confirm-action"
        )
        transitions.extend((
            PlanTransition("confirm-action", StepOutcome.SUCCEEDED, "release"),
            PlanTransition("confirm-action", StepOutcome.DENIED, "withhold"),
            PlanTransition("confirm-action", StepOutcome.EXPIRED, "withhold"),
        ))
    return ExecutionPlan(
        "plan-1", "request-1", route(capability_id), "application-step",
        tuple(steps), tuple(transitions),
    )


def terminal(step_id, disposition):
    return PlanStep(
        step_id, PlanStepKind.FINALIZE, disposition.value,
        terminal_disposition=disposition,
    )


def capability_entry(capability_id):
    if capability_id == OBSERVE:
        descriptor = CapabilityDescriptor(
            OBSERVE, "Observe editor", "Observe active editor",
            CapabilityKind.OBSERVATION, ApplicationAuthority.OBSERVE,
            "observe.input", "observe.output",
        )
    else:
        descriptor = CapabilityDescriptor(
            ACTION, "Edit workspace", "Prepare workspace edit",
            CapabilityKind.ACTION, ApplicationAuthority.MODIFY,
            "edit.input", "edit.output", Reversibility.REVERSIBLE,
            ConfirmationPolicy.ALWAYS, ("document.hash",),
        )
    return CapabilityRegistryEntry(
        "entry-1", "connector-1", "vscode-1", "com.microsoft.vscode", descriptor,
        (RESOURCE,),
    )


def permission_grant(authority, capability_id, expired, subject, resource):
    expires = NOW if expired else NOW + timedelta(hours=1)
    return PermissionGrant(
        "grant-1", subject, (authority,),
        PermissionScope(
            instance_ids=("vscode-1",), capability_ids=(capability_id,),
            resource_uris=(resource,),
        ),
        NOW - timedelta(hours=1), expires_at=expires,
    )


def lifecycle_service():
    ids = iter((
        "instance-1", "start-event", "application-event", "confirmation-event"
    ))
    return PlanLifecycleService(
        InMemoryPlanStateRepository(), clock=lambda: NOW,
        instance_id_factory=lambda: next(ids), event_id_factory=lambda: next(ids),
    )


def observation_command(runtime, expected_revision=0):
    return ObservationAcquisition(
        "instance-1", expected_revision, routed(OBSERVE), "vscode-1", "grant-1",
        {"include": ["selection"]}, RESOURCE,
    )


def action_command(runtime, routed_override=None):
    return ActionProposalAcquisition(
        "instance-1", 0, routed_override or routed(ACTION), "vscode-1", "grant-1",
        "Update selected function", {"edits": 1}, RESOURCE, "7",
    )


def proposal(request):
    return ActionProposal(
        "proposal-1", request, {"diff": "-old\n+new"}, Reversibility.REVERSIBLE,
        ConfirmationPolicy.ALWAYS,
        (ConditionRequirement("document.hash", "sha256", "Hash matches"),),
        reversal_capability_id="vscode.workspace_edit.undo",
    )


if __name__ == "__main__":
    unittest.main()
