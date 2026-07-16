import unittest
from datetime import datetime, timedelta, timezone

from fam_os.core.admission import (
    AdmittedTaskRequest,
    RequestPermissionContext,
)
from fam_os.core.contracts import FailureCategory, TaskRequest
from fam_os.core.routing import CoreRoutingOutcome, CoreRoutingService
from fam_os.routing import RouteDecision, RouteName, RoutingResult


NOW = datetime(2026, 7, 16, 17, tzinfo=timezone.utc)


def admitted(capabilities=("files.read",), valid_until=None, admitted_at=NOW):
    request = TaskRequest("request-1", "Read the selected file", capabilities)
    permission = RequestPermissionContext(
        "principal-1", "session-1", "authority-1", capabilities,
        valid_until or NOW + timedelta(hours=1),
    )
    return AdmittedTaskRequest("admission-1", request, permission, admitted_at)


def result(capabilities=("files.read",)):
    return RoutingResult(RouteDecision(
        RouteName.RETRIEVAL, 0.9, "Requires trusted file retrieval.", capabilities
    ))


class Router:
    def __init__(self, outcome=None, error=None):
        self.outcome = outcome if outcome is not None else result()
        self.error = error
        self.requests = []

    def route(self, request):
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return self.outcome


def service(router):
    return CoreRoutingService(
        router, clock=lambda: NOW, error_id_factory=lambda: "error-1"
    )


class CoreRoutingLifecycleTests(unittest.TestCase):
    def test_routes_only_task_content_and_effective_capabilities(self):
        router = Router()

        outcome = service(router).route(admitted())

        self.assertTrue(outcome.succeeded)
        self.assertEqual("request-1", outcome.routed.request_id)
        self.assertEqual(RouteName.RETRIEVAL, outcome.routed.routing.decision.route)
        sent = router.requests[0]
        self.assertEqual("request-1", sent.request_id)
        self.assertEqual("Read the selected file", sent.prompt)
        self.assertEqual(("files.read",), sent.required_capabilities)
        self.assertFalse(hasattr(sent, "principal_id"))
        self.assertFalse(hasattr(sent, "authority_ref"))

    def test_route_cannot_widen_drop_or_reorder_capabilities(self):
        invalid = (
            ("files.read", "files.write"),
            (),
            ("code.execute", "files.read"),
        )
        request = admitted(("files.read", "code.execute"))
        for capabilities in invalid:
            with self.subTest(capabilities=capabilities):
                outcome = service(Router(result(capabilities))).route(request)
                self.assertFalse(outcome.succeeded)
                self.assertEqual("routing.invalid_result", outcome.failure.code)
                self.assertEqual(FailureCategory.INCOMPATIBLE, outcome.failure.category)

    def test_provider_exception_becomes_safe_unavailable_failure(self):
        router = Router(error=RuntimeError("secret provider path /home/private"))

        outcome = service(router).route(admitted())

        self.assertFalse(outcome.succeeded)
        self.assertEqual("routing.provider_unavailable", outcome.failure.code)
        self.assertEqual(FailureCategory.UNAVAILABLE, outcome.failure.category)
        self.assertNotIn("secret", outcome.failure.safe_message)
        self.assertNotIn("/home", outcome.failure.safe_message)

    def test_non_routing_result_is_incompatible(self):
        outcome = service(Router(outcome={"route": "retrieval"})).route(admitted())
        self.assertFalse(outcome.succeeded)
        self.assertEqual("routing.invalid_result", outcome.failure.code)

    def test_expired_permission_never_reaches_router(self):
        router = Router()
        expired = admitted(
            valid_until=NOW, admitted_at=NOW - timedelta(minutes=1)
        )

        outcome = service(router).route(expired)

        self.assertFalse(outcome.succeeded)
        self.assertEqual("routing.permission_expired", outcome.failure.code)
        self.assertEqual([], router.requests)

    def test_outcome_rejects_ambiguous_state(self):
        with self.assertRaises(ValueError):
            CoreRoutingOutcome("request-1")

    def test_routing_contracts_reject_malformed_evidence(self):
        with self.assertRaises(ValueError):
            RouteDecision(
                RouteName.RETRIEVAL, 0.5, "forged\nreason", ("files.read",)
            )
        with self.assertRaises(ValueError):
            result(("files\nforged",))
        with self.assertRaises(ValueError):
            RoutingResult(
                RouteDecision(RouteName.RETRIEVAL, 0.5, "valid"),
                contract_version="fam.routing/v2",
            )


if __name__ == "__main__":
    unittest.main()
