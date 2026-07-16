import unittest

from fam_os.routing import (
    ROUTING_CONTRACT_VERSION,
    RouteDecision,
    RouteName,
    RoutingRequest,
    RoutingResult,
)


class RouteDecisionTests(unittest.TestCase):
    def test_represents_prototype_routes(self) -> None:
        self.assertEqual(
            {route.value for route in RouteName},
            {"kernel", "code", "math", "retrieval"},
        )

    def test_rejects_invalid_confidence(self) -> None:
        with self.assertRaisesRegex(ValueError, "confidence"):
            RouteDecision(RouteName.CODE, 1.1, "code task")

    def test_normalizes_and_rejects_duplicate_capabilities(self) -> None:
        decision = RouteDecision(RouteName.CODE, 1.0, "code task", (" code ",))
        self.assertEqual(decision.required_capabilities, ("code",))
        with self.assertRaisesRegex(ValueError, "unique"):
            RouteDecision(RouteName.CODE, 1.0, "code task", ("code", "code"))

    def test_routing_family_is_versioned(self) -> None:
        request = RoutingRequest("request-1", "Write code")
        result = RoutingResult(RouteDecision(RouteName.CODE, 1.0, "code task"))
        self.assertEqual(request.contract_version, ROUTING_CONTRACT_VERSION)
        self.assertEqual(result.contract_version, ROUTING_CONTRACT_VERSION)


if __name__ == "__main__":
    unittest.main()
