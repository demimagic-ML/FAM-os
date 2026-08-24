import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

from fam_os.core.engineering import (
    EngineeringAuthorizationDecision,
    EngineeringAuthority,
    EngineeringResourceImpact,
    PostgreSQLIntegrationVerificationService,
)
from tests.contract.schema_database_engineering_fixtures import (
    postgresql_integration_verification_schema_values,
)


NOW = datetime(2026, 7, 19, 21, 0, tzinfo=timezone.utc)


class PostgreSQLIntegrationVerificationServiceTests(unittest.TestCase):
    def test_requires_live_path_bound_modify_before_executor(self):
        plan, candidate, environment, start = _inputs()
        executor = _Executor()
        service = PostgreSQLIntegrationVerificationService(
            _Authorizer(deny=EngineeringAuthority.MODIFY), executor,
            identifier=_identifiers(),
        )

        with self.assertRaisesRegex(PermissionError, "exact live authority"):
            service.execute(
                plan, candidate, environment, start,
                "primary-grant", "resource-grant", "owner-1", "session-1",
                lambda: False,
            )

        self.assertFalse(executor.called)

    def test_records_primary_and_resource_decisions_in_evidence(self):
        plan, candidate, environment, start = _inputs()
        executor = _Executor()
        authorizer = _Authorizer()
        service = PostgreSQLIntegrationVerificationService(
            authorizer, executor, identifier=_identifiers(),
        )

        receipt = service.execute(
            plan, candidate, environment, start,
            "primary-grant", "resource-grant", "owner-1", "session-1",
            lambda: False,
        )

        self.assertTrue(receipt.passed)
        first_pass = authorizer.requests[:5]
        self.assertEqual(
            (
                EngineeringAuthority.EXECUTE,
                EngineeringAuthority.MODIFY,
                EngineeringAuthority.MODIFY,
                EngineeringAuthority.EXECUTE,
                EngineeringAuthority.SECRET_USE,
            ),
            tuple(item.authority for item in first_pass),
        )
        self.assertEqual(
            ("db/001.up.sql", "db/001.down.sql"),
            tuple(item.path for item in first_pass if item.path is not None),
        )


class _Authorizer:
    def __init__(self, deny=None):
        self.deny = deny
        self.requests = []

    def authorize(self, request):
        self.requests.append(request)
        allowed = request.authority is not self.deny
        return EngineeringAuthorizationDecision(
            f"decision-{len(self.requests)}", request.request_id,
            request.grant_id, request.authority, NOW, allowed,
            "authorized" if allowed else "denied",
        )


class _Executor:
    def __init__(self):
        self.called = False

    def execute(
        self, plan, root, environment, receipt, permit, control, decision_ids,
    ):
        self.called = True
        self.assert_live = control.authorization_active()
        return SimpleNamespace(
            passed=True,
            plan_id=plan.plan_id,
            environment_id=plan.environment_id,
            permit_id=permit.permit_id,
            authorization_decision_ids=decision_ids,
        )


def _inputs():
    plan, _receipt = postgresql_integration_verification_schema_values()
    candidate = SimpleNamespace(
        task_id=plan.task_id,
        candidate_id=plan.candidate_id,
        owner_workspace="/owner",
        candidate_workspace="/candidate",
    )
    environment = SimpleNamespace(
        environment_id=plan.environment_id,
        candidate_root="/candidate",
        resource_impact=EngineeringResourceImpact(
            600, 16, 64, 0, 256 * 1024**2, 0,
        ),
    )
    permit = SimpleNamespace(
        permit_id="permit-1", environment_id=plan.environment_id,
    )
    start = SimpleNamespace(
        environment_id=plan.environment_id,
        permit=permit,
        receipt=SimpleNamespace(environment_id=plan.environment_id),
    )
    return plan, candidate, environment, start


def _identifiers():
    counter = iter(range(1, 100))
    return lambda: f"request-{next(counter)}"


if __name__ == "__main__":
    unittest.main()
