import unittest
from datetime import timedelta

from fam_os.applications import (
    ActionConfirmation,
    ApplicationAuthority,
    ConfirmationDecision,
    PermissionGrant,
)
from fam_os.core.lifecycle import (
    ConfirmationCommand,
    ConfirmationDisposition,
    ConfirmationRejection,
    ConfirmationTransitionService,
    InMemoryConfirmationReplayRegistry,
    PermissionExpiryCommand,
    PlanEvidenceKind,
    PlanRejection,
)
from tests.unit.test_core_application_steps import (
    ACTION,
    NOW,
    PermissionRegistry,
    action_command,
    routed,
    setup,
)


class CoreConfirmationTransitionTests(unittest.TestCase):
    def test_approval_is_bound_and_advances_without_executing_action(self):
        runtime, service, provider, route = confirmation_runtime()
        confirmation = decision(ConfirmationDecision.APPROVED)

        result = service.record_confirmation(command(route, confirmation))

        self.assertEqual(ConfirmationDisposition.APPROVED, result.disposition)
        self.assertEqual("release", result.snapshot.current_step_id)
        reference = result.snapshot.events[-1].evidence_refs[0]
        self.assertEqual(PlanEvidenceKind.ACTION_CONFIRMATION, reference.kind)
        self.assertEqual("confirmation-1", reference.reference_id)
        self.assertFalse(hasattr(provider, "execute_action"))

    def test_denial_advances_to_withhold(self):
        _runtime, service, _provider, route = confirmation_runtime()
        confirmation = decision(ConfirmationDecision.DENIED, reason="Do not change it")

        result = service.record_confirmation(command(route, confirmation))

        self.assertEqual(ConfirmationDisposition.DENIED, result.disposition)
        self.assertEqual("withhold", result.snapshot.current_step_id)

    def test_expired_core_permission_becomes_explicit_transition(self):
        _runtime, service, _provider, route = confirmation_runtime(
            clock=NOW + timedelta(hours=2)
        )

        result = service.record_confirmation(
            command(route, decision(ConfirmationDecision.APPROVED))
        )

        self.assertEqual(ConfirmationDisposition.EXPIRED, result.disposition)
        self.assertEqual("withhold", result.snapshot.current_step_id)
        event = result.snapshot.events[-1]
        self.assertEqual(PlanEvidenceKind.PERMISSION_EXPIRY, event.evidence_refs[0].kind)
        self.assertEqual("expired", event.outcome.value)
        self.assertIsNone(result.confirmation)

    def test_explicit_expiry_requires_inactive_permission(self):
        _runtime, active, _provider, route = confirmation_runtime()
        not_expired = active.record_permission_expiry(
            PermissionExpiryCommand("instance-1", 1, route)
        )
        self.assertEqual(ConfirmationRejection.NOT_EXPIRED, not_expired.rejection)

        _runtime, expired, _provider, route = confirmation_runtime(
            clock=NOW + timedelta(hours=2)
        )
        result = expired.record_permission_expiry(
            PermissionExpiryCommand("instance-1", 1, route)
        )
        self.assertEqual(ConfirmationDisposition.EXPIRED, result.disposition)

    def test_inactive_application_grant_expires_while_core_remains_active(self):
        runtime, initial_service, provider, route = confirmation_runtime()
        original = initial_service.permissions.grant
        inactive = PermissionGrant(
            original.grant_id, original.subject_id, original.authorities,
            original.scope, original.issued_at, expires_at=NOW + timedelta(seconds=1),
        )
        service = ConfirmationTransitionService(
            runtime, PermissionRegistry(inactive), InMemoryConfirmationReplayRegistry(),
            clock=lambda: NOW + timedelta(seconds=2),
            evidence_id_factory=lambda: "expiry-1",
        )

        result = service.record_confirmation(
            command(route, decision(ConfirmationDecision.APPROVED))
        )

        self.assertEqual(ConfirmationDisposition.EXPIRED, result.disposition)
        self.assertFalse(hasattr(provider, "execute_action"))

    def test_confirmation_must_match_proposal_grant_principal_and_time(self):
        cases = (
            decision(ConfirmationDecision.APPROVED, proposal_id="other-proposal"),
            decision(ConfirmationDecision.APPROVED, grant_id="other-grant"),
            decision(ConfirmationDecision.APPROVED, decided_by="other-user"),
            decision(
                ConfirmationDecision.APPROVED,
                decided_at=NOW - timedelta(seconds=1),
            ),
            decision(
                ConfirmationDecision.APPROVED,
                decided_at=NOW + timedelta(seconds=1),
            ),
        )
        for confirmation in cases:
            with self.subTest(confirmation=confirmation):
                runtime, service, _provider, route = confirmation_runtime()
                before = runtime.repository.get("instance-1")
                result = service.record_confirmation(command(route, confirmation))
                self.assertEqual(
                    ConfirmationRejection.INVALID_CONFIRMATION, result.rejection
                )
                self.assertEqual(before, runtime.repository.get("instance-1"))

    def test_stale_confirmation_does_not_burn_replay_identity(self):
        _runtime, service, _provider, route = confirmation_runtime()
        confirmation = decision(ConfirmationDecision.APPROVED)
        stale = service.record_confirmation(command(route, confirmation, revision=0))
        accepted = service.record_confirmation(command(route, confirmation, revision=1))
        self.assertEqual(PlanRejection.REVISION_CONFLICT, stale.rejection)
        self.assertEqual(ConfirmationDisposition.APPROVED, accepted.disposition)

    def test_confirmation_cannot_be_replayed_across_plans(self):
        replay = InMemoryConfirmationReplayRegistry()
        _runtime1, service1, _provider1, route1 = confirmation_runtime(replay=replay)
        _runtime2, service2, _provider2, route2 = confirmation_runtime(replay=replay)
        confirmation = decision(ConfirmationDecision.APPROVED)

        first = service1.record_confirmation(command(route1, confirmation))
        second = service2.record_confirmation(command(route2, confirmation))

        self.assertEqual(ConfirmationDisposition.APPROVED, first.disposition)
        self.assertEqual(ConfirmationRejection.REPLAYED, second.rejection)


def confirmation_runtime(clock=NOW, replay=None):
    route = routed(ACTION)
    runtime, application, provider = setup(ACTION, ApplicationAuthority.PROPOSE)
    proposed = application.acquire_action_proposal(action_command(runtime))
    assert proposed.snapshot.current_step_id == "confirm-action"
    service = ConfirmationTransitionService(
        runtime, application.permissions,
        replay or InMemoryConfirmationReplayRegistry(), clock=lambda: clock,
        evidence_id_factory=lambda: "expiry-1",
    )
    return runtime, service, provider, route


def command(route, confirmation, revision=1):
    return ConfirmationCommand("instance-1", revision, route, confirmation)


def decision(
    value, reason=None, proposal_id="proposal-1", grant_id="grant-1",
    decided_by="principal-1", decided_at=NOW,
):
    return ActionConfirmation(
        "confirmation-1", proposal_id, grant_id, value, decided_by, decided_at, reason
    )


if __name__ == "__main__":
    unittest.main()
