import unittest

from fam_os.routing import ModelRouterSettings, ModelTaskRouter, RouteName, RoutingRequest
from fam_os.routing.parsing import RouteParseError, parse_route_decision

from tests.unit.execution_fakes import FakeRuntime


class RouteParsingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.request = RoutingRequest("request-1", "Fix this program", ("python",))

    def test_parses_structured_route_and_preserves_capabilities(self) -> None:
        decision = parse_route_decision(
            '{"route":"code","confidence":0.92,"reason":"programming"}',
            self.request,
        )
        self.assertEqual(decision.route, RouteName.CODE)
        self.assertEqual(decision.confidence, 0.92)
        self.assertEqual(decision.required_capabilities, ("python",))

    def test_recovers_route_from_fenced_or_loose_text(self) -> None:
        decision = parse_route_decision("Result: ```json\n{\"route\":\"math\"}\n```", self.request)
        self.assertEqual(decision.route, RouteName.MATH)
        self.assertEqual(decision.confidence, 0.5)

    def test_rejects_response_without_supported_route(self) -> None:
        with self.assertRaisesRegex(RouteParseError, "supported route"):
            parse_route_decision("I cannot decide", self.request)


class ModelTaskRouterTests(unittest.TestCase):
    def test_uses_provider_neutral_json_inference_request(self) -> None:
        runtime = FakeRuntime(['{"route":"code","confidence":1,"reason":"code"}'])
        router = ModelTaskRouter(
            runtime,
            ModelRouterSettings("router:small", context_tokens=1_024, keep_alive="10m"),
        )

        result = router.route(RoutingRequest("request-1", "Write Python"))

        sent = runtime.requests[0]
        self.assertEqual(result.decision.route, RouteName.CODE)
        self.assertIsNotNone(result.metrics)
        self.assertEqual(result.metrics.model_ref, "router:small")
        self.assertEqual(sent.model_ref, "router:small")
        self.assertEqual(sent.context_tokens, 1_024)
        self.assertEqual(sent.max_output_tokens, 100)
        self.assertTrue(sent.json_output)
        self.assertEqual(len(sent.messages), 2)


if __name__ == "__main__":
    unittest.main()
