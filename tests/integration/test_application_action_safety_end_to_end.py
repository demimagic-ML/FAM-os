import unittest

from fam_os.applications import (
    ActionConfirmation, ActionProposal, ApplicationAuthority, ConditionRequirement,
    ConfirmationDecision, ConfirmationPolicy, PermissionGrant, Reversibility,
)
from fam_os.core.lifecycle import (
    ActionExecutionCommand, ActionProposalAcquisition,
    ApplicationActionExecutionService, ApplicationStepService,
    ConfirmationCommand, ConfirmationTransitionService,
    InMemoryActionExecutionReplayRegistry, InMemoryConfirmationReplayRegistry,
    InMemoryPlanStateRepository, PlanLifecycleService,
)
from tests.unit.test_core_action_execution import (
    Audit, CAPABILITY, NOW, Permissions, Provider, RESOURCE, Verifier, audit_ids,
    capability_entry, event_ids, permission, plan, routed, verified_provider_result,
)


class FullProvider(Provider):
    def prepare_action(self, request):
        return ActionProposal(
            "proposal-1", request, {"summary": "One edit"},
            Reversibility.REVERSIBLE, ConfirmationPolicy.ALWAYS,
            (ConditionRequirement(
                "document.hash", "verifier.hash", "Hash must match.",
            ),),
            (ConditionRequirement(
                "document.revision", "verifier.revision", "Revision must match.",
            ),),
            "app.editor.undo",
        )


class ApplicationActionSafetyEndToEndTests(unittest.TestCase):
    def test_prepare_confirm_execute_verify_audit_and_release(self):
        route = routed()
        lifecycle = PlanLifecycleService(
            InMemoryPlanStateRepository(), clock=lambda: NOW,
            instance_id_factory=lambda: "instance-1", event_id_factory=event_ids(),
        )
        lifecycle.start(route, plan())
        original = permission()
        grant = PermissionGrant(
            original.grant_id, original.subject_id,
            (ApplicationAuthority.PROPOSE, ApplicationAuthority.MODIFY),
            original.scope, original.issued_at, original.expires_at,
        )
        permissions = Permissions(grant)
        provider = FullProvider(capability_entry(), verified_provider_result())
        prepare = ApplicationStepService(
            lifecycle, provider, permissions, clock=lambda: NOW,
            evidence_id_factory=lambda: "prepare-request-1",
        ).acquire_action_proposal(ActionProposalAcquisition(
            "instance-1", 0, route, "editor-1", "grant-1", "Edit main.py",
            {"replacement": "pass"}, RESOURCE, "revision-1",
        ))
        self.assertEqual("confirm", prepare.snapshot.current_step_id)
        confirmation = ActionConfirmation(
            "confirmation-1", "proposal-1", "grant-1",
            ConfirmationDecision.APPROVED, "principal-1", NOW,
        )
        confirmed = ConfirmationTransitionService(
            lifecycle, permissions, InMemoryConfirmationReplayRegistry(),
            clock=lambda: NOW,
        ).record_confirmation(ConfirmationCommand(
            "instance-1", 1, route, confirmation,
        ))
        self.assertEqual("execute", confirmed.snapshot.current_step_id)
        audit = Audit()
        executed = ApplicationActionExecutionService(
            lifecycle, provider, permissions, Verifier(), audit,
            InMemoryActionExecutionReplayRegistry(), clock=lambda: NOW,
            operation_id_factory=lambda: "operation-1", event_id_factory=audit_ids(),
        ).execute(ActionExecutionCommand(
            "instance-1", 2, route, prepare.evidence, confirmation,
        ))
        self.assertTrue(executed.action_result.verified)
        self.assertEqual("release", executed.snapshot.current_step_id)
        self.assertEqual(1, provider.calls)
        self.assertEqual(2, len(audit.intents))
        self.assertEqual(CAPABILITY, audit.intents[-1].capability_id)


if __name__ == "__main__":
    unittest.main()
