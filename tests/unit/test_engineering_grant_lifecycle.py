"""Fake-driven owner grant, revocation, break-glass, and assurance lifecycle."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest

from fam_os.core.engineering import (
    BREAK_GLASS_AUTHORITIES,
    BreakGlassDisposition,
    EngineeringAuthority,
    EngineeringAuthorityGrant,
    EngineeringAuthorizationRequest,
    EngineeringDelegationMode,
    EngineeringExecutionAssurance,
    EngineeringExecutionRecord,
    EngineeringGrantScope,
    EngineeringGrantScopeKind,
    EngineeringResourceImpact,
    GrantLifecycleState,
    OwnerGrantApproval,
    ReversibilityPolicy,
    SecretExposurePolicy,
    VerificationRequirement,
    classify_execution_assurance,
    expand_delegation,
)
from fam_os.core.engineering.grant_policy import (
    EngineeringGrantLedger,
    engineering_grant_digest,
)
from tests.contract.schema_engineering_fixtures import engineering_grant_schema_values


NOW = datetime(2026, 7, 18, 10, 0, tzinfo=timezone.utc)


class FakeOwnerAuthorityVerifier:
    def __init__(self) -> None:
        self.grant_approval_ids: set[str] = set()
        self.break_glass_decision_ids: set[str] = set()

    def verify_grant(self, approval, grant_sha256: str) -> bool:
        return (
            approval.approval_id in self.grant_approval_ids
            and approval.grant_sha256 == grant_sha256
        )

    def verify_break_glass(self, _challenge, decision) -> bool:
        return decision.decision_id in self.break_glass_decision_ids


def impact(**overrides) -> EngineeringResourceImpact:
    values = {
        "max_wall_seconds": 300,
        "max_tool_runs": 5,
        "max_processes": 2,
        "max_changed_files": 4,
        "max_changed_bytes": 10_000,
        "max_network_bytes": 0,
    }
    values.update(overrides)
    return EngineeringResourceImpact(**values)


def safe_grant(
    *, kind=EngineeringGrantScopeKind.TASK, scope_id="task-1",
) -> EngineeringAuthorityGrant:
    scope = EngineeringGrantScope(
        kind, scope_id, ("/workspace",), ("src/**",), (".git/**",),
        ("python3",), (), (), (), (), (),
    )
    return EngineeringAuthorityGrant(
        "grant-safe-1", "owner-1", "fam-core",
        EngineeringDelegationMode.WORKSPACE_OPERATOR,
        expand_delegation(EngineeringDelegationMode.WORKSPACE_OPERATOR),
        scope, "Modify and test the selected workspace", NOW,
        NOW + timedelta(hours=1), GrantLifecycleState.ACTIVE,
        ReversibilityPolicy.REQUIRED, SecretExposurePolicy.NONE,
        VerificationRequirement.REQUIRED, impact(), False,
    )


def owner_approval(grant, approval_id="approval-trusted") -> OwnerGrantApproval:
    return OwnerGrantApproval(
        approval_id, grant.grant_id, grant.owner_id,
        engineering_grant_digest(grant), NOW + timedelta(minutes=1),
        "authenticated-owner-session",
    )


def authorization(grant, **overrides) -> EngineeringAuthorizationRequest:
    values = {
        "request_id": "authorization-request-1",
        "grant_id": grant.grant_id,
        "principal_id": grant.principal_id,
        "authority": EngineeringAuthority.MODIFY,
        "task_id": "task-1",
        "session_id": "session-1",
        "action_id": None,
        "change_set_id": None,
        "workspace_root": "/workspace",
        "path": "src/example.py",
        "toolchain": "python3",
        "network_host": None,
        "package_registry": None,
        "git_remote": None,
        "git_branch": None,
        "secret_ref": None,
        "resource_impact": impact(max_wall_seconds=60, max_tool_runs=1),
    }
    values.update(overrides)
    return EngineeringAuthorizationRequest(**values)


class EngineeringGrantLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = [NOW + timedelta(minutes=2)]
        self.verifier = FakeOwnerAuthorityVerifier()
        self.ids = iter(f"decision-{index}" for index in range(100))
        self.ledger = EngineeringGrantLedger(
            self.verifier, clock=lambda: self.now[0], identifier=lambda: next(self.ids),
        )

    def activate(self, grant=None):
        grant = grant or safe_grant()
        approval = owner_approval(grant)
        self.verifier.grant_approval_ids.add(approval.approval_id)
        self.ledger.activate(grant, approval)
        return grant

    def test_visible_profiles_expand_to_individual_authorities(self) -> None:
        self.assertEqual(
            (EngineeringAuthority.OBSERVE, EngineeringAuthority.PROPOSE),
            expand_delegation(EngineeringDelegationMode.SAFE_DEFAULT),
        )
        self.assertEqual(
            set(EngineeringAuthority),
            set(expand_delegation(EngineeringDelegationMode.FULL_OWNER)),
        )
        with self.assertRaisesRegex(ValueError, "hidden overrides"):
            expand_delegation(
                EngineeringDelegationMode.SAFE_DEFAULT,
                (EngineeringAuthority.HOST_ADMIN,),
            )

    def test_prompt_repository_model_and_tool_output_cannot_activate_authority(self) -> None:
        grant = safe_grant()
        for source in ("prompt", "repository", "model", "tool"):
            with self.subTest(source=source):
                forged = owner_approval(grant, f"forged-from-{source}")
                with self.assertRaisesRegex(PermissionError, "owner approval"):
                    self.ledger.activate(grant, forged)
        self.assertIsNone(self.ledger.get(grant.grant_id))

    def test_admitted_grant_is_exactly_scoped_and_budgeted(self) -> None:
        grant = self.activate()
        self.assertTrue(self.ledger.authorize(authorization(grant)).allowed)
        denied_path = self.ledger.authorize(
            authorization(grant, request_id="path", path=".git/config"),
        )
        denied_budget = self.ledger.authorize(
            authorization(
                grant, request_id="budget",
                resource_impact=impact(max_changed_bytes=20_000),
            ),
        )
        self.assertEqual("path_denied", denied_path.reason_code)
        self.assertEqual("resource_budget_exceeded", denied_budget.reason_code)

    def test_revocation_and_expiry_immediately_deny_future_use(self) -> None:
        grant = self.activate()
        self.ledger.revoke(grant.grant_id, grant.owner_id)
        self.assertEqual(
            "grant_inactive", self.ledger.authorize(authorization(grant)).reason_code,
        )

        second = replace(grant, grant_id="grant-safe-2")
        second_approval = owner_approval(second, "approval-second")
        self.verifier.grant_approval_ids.add(second_approval.approval_id)
        self.ledger.activate(second, second_approval)
        self.now[0] = second.expires_at
        self.assertEqual(
            "grant_inactive", self.ledger.authorize(authorization(second)).reason_code,
        )

    def test_action_grant_is_consumed_without_widening(self) -> None:
        grant = safe_grant(kind=EngineeringGrantScopeKind.ACTION, scope_id="action-1")
        self.activate(grant)
        request = authorization(grant, action_id="action-1")
        self.assertTrue(self.ledger.authorize(request).allowed)
        consumed = self.ledger.consume(grant.grant_id, "effect-1")
        self.assertEqual(GrantLifecycleState.CONSUMED, consumed.state)
        self.assertEqual(
            "grant_inactive", self.ledger.authorize(request).reason_code,
        )

    def test_break_glass_binds_exact_consequences_and_scope(self) -> None:
        grant, approval, _request, _authorization, challenge, decision, _execution = (
            engineering_grant_schema_values()
        )
        self.verifier.grant_approval_ids.add(approval.approval_id)
        with self.assertRaisesRegex(PermissionError, "break-glass"):
            self.ledger.activate(grant, approval, challenge, decision)
        self.verifier.break_glass_decision_ids.add(decision.decision_id)
        self.ledger.activate(grant, approval, challenge, decision)
        self.assertIsNotNone(self.ledger.get(grant.grant_id))

        denied = replace(decision, disposition=BreakGlassDisposition.DENIED)
        second = replace(
            grant, grant_id="grant-engineering-2",
            break_glass_decision_id=denied.decision_id,
        )
        second_approval = replace(
            approval, approval_id="approval-high-2", grant_id=second.grant_id,
            grant_sha256=engineering_grant_digest(second),
        )
        self.verifier.grant_approval_ids.add(second_approval.approval_id)
        with self.assertRaisesRegex(PermissionError, "break-glass"):
            self.ledger.activate(second, second_approval, challenge, denied)

    def test_break_glass_scope_choices_are_individual_not_a_master_session_flag(self) -> None:
        self.assertEqual(
            {"action", "changeset", "task", "session"},
            {item.value for item in EngineeringGrantScopeKind},
        )
        self.assertTrue({
            EngineeringAuthority.HOST_ADMIN,
            EngineeringAuthority.PRODUCTION_MUTATE,
            EngineeringAuthority.POLICY_CHANGE,
            EngineeringAuthority.PROTECTED_REF_WRITE,
        } <= BREAK_GLASS_AUTHORITIES)

    def test_assurance_never_derives_verified_from_owner_authority(self) -> None:
        self.assertEqual(
            EngineeringExecutionAssurance.EXECUTED_UNVERIFIED,
            classify_execution_assurance(
                verifier_passed=False, waiver_decision_id=None,
            ),
        )
        self.assertEqual(
            EngineeringExecutionAssurance.VERIFICATION_WAIVED,
            classify_execution_assurance(
                verifier_passed=False, waiver_decision_id="waiver-1",
            ),
        )
        self.assertEqual(
            EngineeringExecutionAssurance.VERIFIED,
            classify_execution_assurance(
                verifier_passed=True, waiver_decision_id=None,
            ),
        )

    def test_execution_record_cannot_relabel_unverified_effect_as_verified(self) -> None:
        with self.assertRaisesRegex(ValueError, "passing verifier evidence"):
            EngineeringExecutionRecord(
                "execution-1", "task-1", "grant-1", "effect-1", self.now[0],
                True, EngineeringExecutionAssurance.VERIFIED, (), ("effect-1",),
            )
        with self.assertRaisesRegex(ValueError, "explicit waiver"):
            EngineeringExecutionRecord(
                "execution-2", "task-1", "grant-1", "effect-1", self.now[0],
                True, EngineeringExecutionAssurance.VERIFICATION_WAIVED,
                (), ("effect-1",),
            )


if __name__ == "__main__":
    unittest.main()
