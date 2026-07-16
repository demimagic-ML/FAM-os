import unittest
from datetime import datetime, timedelta, timezone

from fam_os.applications import (
    APPLICATION_FAILURE_CONTRACT_VERSION,
    ActionConfirmation,
    ActionPreparationRequest,
    ActionProposal,
    ActionResult,
    ActionStatus,
    ApplicationAuthority,
    ApplicationFailure,
    ApplicationFailureCategory,
    ApplicationRetryDisposition,
    ConditionEvidence,
    ConditionRequirement,
    ConfirmationDecision,
    ConfirmationPolicy,
    ObservationRequest,
    ObservationResult,
    ObservationStatus,
    PermissionGrant,
    PermissionScope,
    Reversibility,
)


NOW = datetime(2026, 7, 16, 10, 0, tzinfo=timezone.utc)


class PermissionGrantTests(unittest.TestCase):
    def test_grant_has_scope_and_expires(self) -> None:
        grant = PermissionGrant(
            "grant-1",
            "user-1",
            (ApplicationAuthority.OBSERVE, ApplicationAuthority.MODIFY),
            PermissionScope(
                application_ids=("com.microsoft.vscode",),
                resource_uris=("file:///workspace/fam-os",),
            ),
            NOW,
            expires_at=NOW + timedelta(minutes=10),
        )
        self.assertTrue(grant.active_at(NOW + timedelta(minutes=1)))
        self.assertFalse(grant.active_at(NOW + timedelta(minutes=10)))

    def test_rejects_global_unscoped_grant(self) -> None:
        with self.assertRaisesRegex(ValueError, "scope"):
            PermissionScope()

    def test_rejects_naive_permission_time(self) -> None:
        with self.assertRaisesRegex(ValueError, "timezone"):
            PermissionGrant(
                "grant-1",
                "user-1",
                (ApplicationAuthority.OBSERVE,),
                PermissionScope(capability_ids=("vscode.editor.active",)),
                datetime(2026, 7, 16),
            )


class ObservationContractTests(unittest.TestCase):
    def test_freezes_nested_observation_parameters(self) -> None:
        parameters = {"include": ["selection", "language"]}
        request = ObservationRequest(
            "request-1", "vscode-1", "vscode.editor.active", "grant-1", parameters
        )
        parameters["include"].append("text")
        self.assertEqual(request.parameters["include"], ("selection", "language"))
        with self.assertRaises(TypeError):
            request.parameters["new"] = "value"  # type: ignore[index]

    def test_failed_observation_cannot_expose_payload(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot expose payload"):
            ObservationResult(
                "request-1",
                ObservationStatus.DENIED,
                NOW,
                {"text": "private"},
                error=ApplicationFailure(
                    ApplicationFailureCategory.PERMISSION_DENIED,
                    "application.permission.denied",
                    "Permission was denied.",
                    ApplicationRetryDisposition.AFTER_USER_ACTION,
                ),
            )

    def test_denied_observation_requires_permission_failure_category(self) -> None:
        failure = ApplicationFailure(
            ApplicationFailureCategory.EXECUTION_FAILED,
            "application.connector.failed",
            "The connector failed.",
            ApplicationRetryDisposition.WITH_BACKOFF,
        )
        with self.assertRaisesRegex(ValueError, "permission-denied"):
            ObservationResult("request-1", ObservationStatus.DENIED, NOW, error=failure)


class ActionContractTests(unittest.TestCase):
    def test_application_failure_contract_is_versioned(self) -> None:
        failure = ApplicationFailure(
            ApplicationFailureCategory.EXECUTION_FAILED,
            "application.connector.failed",
            "The connector failed.",
            ApplicationRetryDisposition.WITH_BACKOFF,
        )
        self.assertEqual(failure.contract_version, APPLICATION_FAILURE_CONTRACT_VERSION)

    def test_recoverable_proposal_requires_reversal_capability(self) -> None:
        for reversibility in (
            Reversibility.REVERSIBLE, Reversibility.COMPENSATABLE,
        ):
            with self.subTest(reversibility=reversibility):
                with self.assertRaisesRegex(ValueError, "reversal capability"):
                    ActionProposal(
                        "proposal-1",
                        _action_request(),
                        {"diff": "-old\n+new"},
                        reversibility,
                        ConfirmationPolicy.ALWAYS,
                        (_hash_condition(),),
                    )

    def test_denial_requires_reason(self) -> None:
        with self.assertRaisesRegex(ValueError, "reason"):
            ActionConfirmation(
                "confirm-1",
                "proposal-1",
                "grant-1",
                ConfirmationDecision.DENIED,
                "user-1",
                NOW,
            )

    def test_verified_action_requires_passing_postconditions(self) -> None:
        with self.assertRaisesRegex(ValueError, "passing postconditions"):
            ActionResult(
                "proposal-1",
                ActionStatus.VERIFIED,
                NOW,
                (ConditionEvidence("document.hash", "sha256", False, "hash mismatch"),),
            )

    def test_postcondition_failure_is_not_verified(self) -> None:
        result = ActionResult(
            "proposal-1",
            ActionStatus.POSTCONDITION_FAILED,
            NOW,
            (ConditionEvidence("document.hash", "sha256", False, "hash mismatch"),),
            reversal_token="undo-1",
            error=ApplicationFailure(
                ApplicationFailureCategory.POSTCONDITION_FAILED,
                "application.postcondition.document-hash-failed",
                "The document hash did not match the approved preview.",
                ApplicationRetryDisposition.AFTER_STATE_CHANGE,
            ),
        )
        self.assertFalse(result.verified)
        self.assertEqual(result.reversal_token, "undo-1")

    def test_action_status_matches_failure_category(self) -> None:
        failure = ApplicationFailure(
            ApplicationFailureCategory.EXECUTION_FAILED,
            "application.connector.failed",
            "The connector failed.",
            ApplicationRetryDisposition.WITH_BACKOFF,
        )
        with self.assertRaisesRegex(ValueError, "must match"):
            ActionResult("proposal-1", ActionStatus.CANCELLED, NOW, error=failure)

    def test_application_failure_rejects_raw_multiline_details(self) -> None:
        with self.assertRaisesRegex(ValueError, "bounded line"):
            ApplicationFailure(
                ApplicationFailureCategory.EXECUTION_FAILED,
                "application.connector.failed",
                "safe\nTraceback: secret path",
                ApplicationRetryDisposition.WITH_BACKOFF,
            )


def _action_request() -> ActionPreparationRequest:
    return ActionPreparationRequest(
        "request-1",
        "vscode-1",
        "vscode.workspace_edit.apply",
        "grant-1",
        "Update the selected function",
        {"edits": [{"start": 1, "end": 2, "text": "new"}]},
        "file:///workspace/fam-os/app.py",
        "document-version-7",
    )


def _hash_condition() -> ConditionRequirement:
    return ConditionRequirement(
        "document.hash", "sha256", "Document hash matches the approved preview"
    )


if __name__ == "__main__":
    unittest.main()
