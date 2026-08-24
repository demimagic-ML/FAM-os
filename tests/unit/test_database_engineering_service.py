import unittest
from datetime import datetime, timezone
from pathlib import Path

from fam_os.core.engineering import DatabaseEngineeringService
from fam_os.core.engineering.grants import EngineeringAuthorizationDecision
from fam_os.core.engineering.transactions import CandidateWorkspace
from tests.contract.schema_database_engineering_fixtures import (
    database_engineering_schema_values,
)


NOW = datetime(2026, 7, 19, 19, 0, tzinfo=timezone.utc)


class RecordingAuthorizer:
    def __init__(self, allowed: bool = True) -> None:
        self.allowed = allowed
        self.requests = []

    def authorize(self, request):
        self.requests.append(request)
        return EngineeringAuthorizationDecision(
            f"decision-{len(self.requests)}", request.request_id,
            request.grant_id, request.authority, NOW, self.allowed,
            "authorized" if self.allowed else "revoked",
        )


class RecordingExecutor:
    def __init__(self) -> None:
        self.call = None

    def execute(self, plan, root, permit, control):
        self.call = (plan, root, permit)
        if not control.authorization_active():
            raise PermissionError("live authority disappeared")
        return permit


class DatabaseEngineeringServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        _target, self.plan, _permit, _backup, _receipt = database_engineering_schema_values()
        self.candidate = CandidateWorkspace(
            self.plan.candidate_id, self.plan.task_id, "baseline-1",
            "/owner/workspace", "/candidate/workspace", NOW,
            "copy", "a" * 64, (),
        )

    def test_mints_permit_only_after_exact_execute_and_modify_decisions(self) -> None:
        authorizer = RecordingAuthorizer()
        executor = RecordingExecutor()
        identifiers = iter(("execute-request", "modify-request", "permit-1"))
        service = DatabaseEngineeringService(
            authorizer, executor, clock=lambda: NOW,
            identifier=lambda: next(identifiers),
        )
        permit = service.execute(
            self.plan, self.candidate, "grant-1", "principal-1", "session-1",
            lambda: False,
        )
        initial = authorizer.requests[:2]
        self.assertEqual(
            tuple(request.authority.value for request in initial),
            ("execute", "modify"),
        )
        self.assertTrue(all(
            request.change_set_id == self.plan.approved_changeset_id
            and request.path == self.plan.target.database_name
            and request.workspace_root == self.candidate.owner_workspace
            and request.resource_impact == self.plan.execution_resource_impact
            for request in initial
        ))
        self.assertEqual(permit.permit_id, "permit-1")
        self.assertEqual(executor.call[1], Path(self.candidate.candidate_workspace))

    def test_denial_has_no_executor_effect(self) -> None:
        authorizer = RecordingAuthorizer(False)
        executor = RecordingExecutor()
        service = DatabaseEngineeringService(
            authorizer, executor, clock=lambda: NOW,
        )
        with self.assertRaisesRegex(PermissionError, "exact live authority"):
            service.execute(
                self.plan, self.candidate, "grant-1", "principal-1", "session-1",
                lambda: False,
            )
        self.assertIsNone(executor.call)

    def test_candidate_identity_mismatch_precedes_authorization(self) -> None:
        authorizer = RecordingAuthorizer()
        executor = RecordingExecutor()
        service = DatabaseEngineeringService(
            authorizer, executor, clock=lambda: NOW,
        )
        mismatched = CandidateWorkspace(
            "different", self.candidate.task_id, self.candidate.baseline_id,
            self.candidate.owner_workspace, self.candidate.candidate_workspace,
            NOW, "copy", "a" * 64, (),
        )
        with self.assertRaisesRegex(ValueError, "does not match"):
            service.execute(
                self.plan, mismatched, "grant-1", "principal-1", "session-1",
                lambda: False,
            )
        self.assertEqual(authorizer.requests, [])


if __name__ == "__main__":
    unittest.main()
