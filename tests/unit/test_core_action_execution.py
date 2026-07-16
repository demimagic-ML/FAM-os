import unittest
from datetime import datetime, timedelta, timezone

from fam_os.applications import (
    ActionConfirmation, ActionProposal, ActionPreparationRequest, ActionResult,
    ActionStatus, ApplicationActionAuditRecord, ApplicationAuthority,
    CapabilityDescriptor, CapabilityKind, CapabilityRegistryEntry,
    ConditionEvidence, ConditionRequirement, ConfirmationDecision,
    ConfirmationPolicy, PermissionGrant, PermissionScope, Reversibility,
)
from fam_os.core.admission import AdmittedTaskRequest, RequestPermissionContext
from fam_os.core.contracts import (
    ExecutionPlan, PlanStep, PlanStepKind, PlanTransition, StepOutcome, TaskRequest,
    TerminalDisposition,
)
from fam_os.core.lifecycle import (
    ActionExecutionCommand, ActionExecutionRejection,
    ApplicationActionExecutionService, InMemoryActionExecutionReplayRegistry,
    InMemoryPlanStateRepository, PlanEvidenceKind, PlanEvidenceReference,
    PlanLifecycleService,
)
from fam_os.core.routing import RoutedTaskRequest
from fam_os.routing import RouteDecision, RouteName, RoutingResult


NOW = datetime(2026, 7, 16, 12, 0, tzinfo=timezone.utc)
CAPABILITY = "app.editor.modify"
RESOURCE = "file:///workspace/main.py"


class Provider:
    def __init__(self, entry, result=None, raises=False):
        self.entry = entry
        self.result = result
        self.raises = raises
        self.calls = 0

    def capability(self, instance_id, capability_id):
        return self.entry

    def execute_action(self, proposal, confirmation):
        self.calls += 1
        if self.raises:
            raise RuntimeError("provider detail must not escape")
        return self.result


class Verifier:
    def __init__(self, outcomes=None):
        self.outcomes = outcomes or {}

    def verify(self, requirement, proposal, provider_result):
        passed = self.outcomes.get(requirement.condition_id, True)
        return ConditionEvidence(
            requirement.condition_id, requirement.verifier_id, passed,
            "Condition passed." if passed else "Condition failed.",
        )


class Permissions:
    def __init__(self, grant):
        self.grant = grant

    def get(self, grant_id):
        return self.grant if grant_id == self.grant.grant_id else None


class Audit:
    def __init__(self, fail_at=None):
        self.intents = []
        self.fail_at = fail_at

    def append(self, value):
        if self.fail_at == len(self.intents) + 1:
            raise RuntimeError("audit unavailable")
        self.intents.append(value)
        sequence = len(self.intents)
        return ApplicationActionAuditRecord(
            sequence, "0" * 64, f"{sequence:x}".rjust(64, "0"), value,
        )


class CoreActionExecutionTests(unittest.TestCase):
    def test_directory_resource_scope_allows_only_declared_descendants(self):
        from fam_os.core.lifecycle.application_authorization import _resource_scope_allows
        from dataclasses import replace
        self.assertTrue(_resource_scope_allows(
            "file:///workspace/", "file:///workspace/src/main.py",
        ))
        self.assertFalse(_resource_scope_allows(
            "file:///workspace/", "file:///workspace/../secret.txt",
        ))
        self.assertFalse(_resource_scope_allows(
            "file:///workspace/file.txt", "file:///workspace/file.txt/child",
        ))
        runtime = action_runtime()
        runtime.provider.entry = replace(
            runtime.provider.entry, resource_scopes=("file:///workspace/",),
        )
        outcome = runtime.service.execute(runtime.command)
        self.assertTrue(outcome.action_result.verified)

        denied = action_runtime()
        denied.provider.entry = replace(
            denied.provider.entry, resource_scopes=("file:///other/",),
        )
        outcome = denied.service.execute(denied.command)
        self.assertIs(ActionExecutionRejection.PERMISSION_DENIED, outcome.rejection)

    def test_verified_action_advances_only_after_trusted_conditions_and_audit(self):
        runtime = action_runtime()
        outcome = runtime.service.execute(runtime.command)
        self.assertTrue(outcome.action_result.verified)
        self.assertEqual("release", outcome.snapshot.current_step_id)
        self.assertEqual(1, runtime.provider.calls)
        self.assertEqual(2, len(outcome.audit_event_ids))
        self.assertEqual("undo-token", outcome.recovery.reversal_token)
        kinds = tuple(ref.kind for ref in outcome.snapshot.events[-1].evidence_refs)
        self.assertEqual(
            (PlanEvidenceKind.ACTION_RESULT, PlanEvidenceKind.ACTION_AUDIT, PlanEvidenceKind.ACTION_AUDIT),
            kinds,
        )
        self.assertNotEqual(RESOURCE, runtime.audit.intents[0].resource_sha256)

    def test_failed_precondition_never_calls_provider_and_advances_withhold(self):
        runtime = action_runtime(outcomes={"document.revision": False})
        outcome = runtime.service.execute(runtime.command)
        self.assertIs(ActionStatus.PRECONDITION_FAILED, outcome.action_result.status)
        self.assertFalse(outcome.provider_invoked)
        self.assertEqual(0, runtime.provider.calls)
        self.assertEqual("withhold", outcome.snapshot.current_step_id)

    def test_failed_postcondition_withholds_and_requires_recovery(self):
        runtime = action_runtime(outcomes={"document.hash": False})
        outcome = runtime.service.execute(runtime.command)
        self.assertIs(ActionStatus.POSTCONDITION_FAILED, outcome.action_result.status)
        self.assertEqual("withhold", outcome.snapshot.current_step_id)
        self.assertTrue(outcome.recovery.compensation_required)
        self.assertEqual("app.editor.undo", outcome.recovery.reversal_capability_id)
        self.assertEqual({}, outcome.action_result.output)

    def test_required_request_audit_failure_prevents_provider(self):
        runtime = action_runtime(audit=Audit(fail_at=1))
        outcome = runtime.service.execute(runtime.command)
        self.assertIs(ActionExecutionRejection.AUDIT_UNAVAILABLE, outcome.rejection)
        self.assertEqual(0, runtime.provider.calls)
        self.assertEqual("execute", runtime.lifecycle.repository.get("instance-1").current_step_id)

    def test_terminal_audit_failure_withholds_mutated_action_and_preserves_undo(self):
        runtime = action_runtime(audit=Audit(fail_at=2))
        outcome = runtime.service.execute(runtime.command)
        self.assertIs(ActionExecutionRejection.AUDIT_UNAVAILABLE, outcome.rejection)
        self.assertEqual("withhold", outcome.snapshot.current_step_id)
        self.assertEqual("undo-token", outcome.recovery.reversal_token)
        self.assertTrue(outcome.recovery.compensation_required)
        self.assertFalse(outcome.action_result.verified)

    def test_stale_or_wrong_confirmation_never_reaches_provider(self):
        runtime = action_runtime()
        wrong = ActionConfirmation(
            "confirmation-x", "proposal-x", "grant-1", ConfirmationDecision.APPROVED,
            "principal-1", NOW,
        )
        command = ActionExecutionCommand(
            "instance-1", 2, runtime.command.routed, runtime.command.proposal, wrong,
        )
        outcome = runtime.service.execute(command)
        self.assertIs(ActionExecutionRejection.INVALID_EVIDENCE, outcome.rejection)
        self.assertEqual(0, runtime.provider.calls)

    def test_execution_replay_is_audited_but_never_calls_provider(self):
        runtime = action_runtime()
        runtime.service.replay.reserve("confirmation-1")
        outcome = runtime.service.execute(runtime.command)
        self.assertIs(ActionExecutionRejection.REPLAYED, outcome.rejection)
        self.assertEqual(0, runtime.provider.calls)
        self.assertEqual(2, len(runtime.audit.intents))
        self.assertEqual("execute", runtime.lifecycle.repository.get("instance-1").current_step_id)


class Runtime:
    pass


def action_runtime(outcomes=None, audit=None):
    value = Runtime()
    value.route = routed()
    value.lifecycle = PlanLifecycleService(
        InMemoryPlanStateRepository(), clock=lambda: NOW,
        instance_id_factory=lambda: "instance-1", event_id_factory=event_ids(),
    )
    started = value.lifecycle.start(value.route, plan())
    proposal = action_proposal()
    value.lifecycle.advance(
        "instance-1", 0, StepOutcome.SUCCEEDED,
        (PlanEvidenceReference("proposal-1", PlanEvidenceKind.ACTION_PROPOSAL, CAPABILITY, "grant-1"),),
    )
    confirmation = action_confirmation()
    value.lifecycle.advance(
        "instance-1", 1, StepOutcome.SUCCEEDED,
        (PlanEvidenceReference("confirmation-1", PlanEvidenceKind.ACTION_CONFIRMATION, CAPABILITY, "grant-1"),),
    )
    assert started.snapshot is not None
    entry = capability_entry()
    provider_result = verified_provider_result()
    value.provider = Provider(entry, provider_result)
    value.audit = audit or Audit()
    value.service = ApplicationActionExecutionService(
        value.lifecycle, value.provider, Permissions(permission()), Verifier(outcomes),
        value.audit, InMemoryActionExecutionReplayRegistry(), clock=lambda: NOW,
        operation_id_factory=lambda: "operation-1", event_id_factory=audit_ids(),
    )
    value.command = ActionExecutionCommand(
        "instance-1", 2, value.route, proposal, confirmation,
    )
    return value


def routed():
    request = TaskRequest("request-1", "Edit the file", (CAPABILITY,))
    context = RequestPermissionContext(
        "principal-1", "session-1", "authority-1", (CAPABILITY,), NOW + timedelta(hours=1),
    )
    admitted = AdmittedTaskRequest("admission-1", request, context, NOW - timedelta(minutes=1))
    decision = RouteDecision(RouteName.CODE, 0.9, "Use editor.", (CAPABILITY,))
    return RoutedTaskRequest(admitted, RoutingResult(decision))


def plan():
    steps = (
        PlanStep("prepare", PlanStepKind.PREPARE_ACTION, "Prepare", (CAPABILITY,)),
        PlanStep("confirm", PlanStepKind.CONFIRM_ACTION, "Confirm", (CAPABILITY,)),
        PlanStep(
            "execute", PlanStepKind.EXECUTE_ACTION, "Execute", (CAPABILITY,),
            ("document.hash",),
        ),
        terminal("release", TerminalDisposition.RELEASE),
        terminal("withhold", TerminalDisposition.WITHHOLD),
    )
    transitions = (
        PlanTransition("prepare", StepOutcome.SUCCEEDED, "confirm"),
        PlanTransition("confirm", StepOutcome.SUCCEEDED, "execute"),
        PlanTransition("execute", StepOutcome.SUCCEEDED, "release"),
        PlanTransition("execute", StepOutcome.FAILED, "withhold"),
    )
    decision = RouteDecision(RouteName.CODE, 0.9, "Use editor.", (CAPABILITY,))
    return ExecutionPlan("plan-1", "request-1", decision, "prepare", steps, transitions)


def terminal(step_id, disposition):
    return PlanStep(
        step_id, PlanStepKind.FINALIZE, disposition.value,
        terminal_disposition=disposition,
    )


def capability_entry():
    descriptor = CapabilityDescriptor(
        CAPABILITY, "Modify editor", "Modify exact document", CapabilityKind.ACTION,
        ApplicationAuthority.MODIFY, "edit.input", "edit.output",
        Reversibility.REVERSIBLE, ConfirmationPolicy.ALWAYS, ("document.hash",),
    )
    return CapabilityRegistryEntry(
        "entry-1", "connector-1", "editor-1", "app.editor", descriptor, (RESOURCE,),
    )


def permission():
    return PermissionGrant(
        "grant-1", "principal-1", (ApplicationAuthority.MODIFY,),
        PermissionScope(
            application_ids=("app.editor",), instance_ids=("editor-1",),
            capability_ids=(CAPABILITY,), resource_uris=(RESOURCE,),
        ),
        NOW - timedelta(minutes=1), NOW + timedelta(hours=1),
    )


def action_proposal():
    request = ActionPreparationRequest(
        "prepare-request-1", "editor-1", CAPABILITY, "grant-1", "Edit main.py",
        {"replacement": "pass"}, RESOURCE, "revision-1",
    )
    precondition = ConditionRequirement(
        "document.revision", "verifier.revision", "Revision must match.",
    )
    postcondition = ConditionRequirement(
        "document.hash", "verifier.hash", "Hash must match.",
    )
    return ActionProposal(
        "proposal-1", request, {"summary": "One edit"}, Reversibility.REVERSIBLE,
        ConfirmationPolicy.ALWAYS, (postcondition,), (precondition,), "app.editor.undo",
    )


def action_confirmation():
    return ActionConfirmation(
        "confirmation-1", "proposal-1", "grant-1", ConfirmationDecision.APPROVED,
        "principal-1", NOW,
    )


def verified_provider_result():
    evidence = ConditionEvidence("document.hash", "provider.hash", True, "Provider matched.")
    return ActionResult(
        "proposal-1", ActionStatus.VERIFIED, NOW, (evidence,), {"changed": True},
        "revision-1", "revision-2", "undo-token",
    )


def event_ids():
    values = iter(("plan-start", "plan-proposal", "plan-confirm", "plan-execute"))
    return lambda: next(values)


def audit_ids():
    values = iter(("audit-request", "audit-terminal", "audit-extra"))
    return lambda: next(values)


if __name__ == "__main__":
    unittest.main()
