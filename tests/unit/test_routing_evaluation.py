import unittest

from fam_os.routing import RouteName
from fam_os.routing.evaluation import (
    evaluate_routing_model,
    parse_routing_cases,
    summarize_routing_model,
)
from fam_os.routing.inference import ModelRouterSettings

from tests.unit.execution_fakes import FakeRuntime


class RoutingEvaluationTests(unittest.TestCase):
    def test_parses_evaluates_and_summarizes_balanced_cases(self) -> None:
        cases = parse_routing_cases(
            (
                '{"id":"k","expected_route":"kernel","prompt":"rewrite"}',
                '{"id":"c","expected_route":"code","prompt":"debug"}',
                '{"id":"m","expected_route":"math","prompt":"calculate"}',
                '{"id":"r","expected_route":"retrieval","prompt":"inspect files"}',
            )
        )
        runtime = FakeRuntime(
            [
                '{"route":"kernel","confidence":1,"reason":"language"}',
                '{"route":"code","confidence":1,"reason":"program"}',
                "math",
                "undecidable",
            ]
        )

        results = evaluate_routing_model(runtime, ModelRouterSettings("router"), cases)
        summary = summarize_routing_model("router", results)

        self.assertEqual(summary.correct, 3)
        self.assertEqual(summary.total, 4)
        self.assertEqual(summary.accuracy, 0.75)
        self.assertEqual(summary.structured_rate, 0.5)
        self.assertEqual(results[2].predicted_route, RouteName.MATH)
        self.assertIsNone(results[3].predicted_route)

    def test_rejects_duplicate_case_ids(self) -> None:
        lines = (
            '{"id":"same","expected_route":"code","prompt":"one"}',
            '{"id":"same","expected_route":"math","prompt":"two"}',
        )
        with self.assertRaisesRegex(ValueError, "unique"):
            parse_routing_cases(lines)

    def test_rejects_invalid_case_with_line_number(self) -> None:
        with self.assertRaisesRegex(ValueError, "line 2"):
            parse_routing_cases(("", '{"id":"x","expected_route":"unknown","prompt":"x"}'))


if __name__ == "__main__":
    unittest.main()
