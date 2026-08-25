import json
import tempfile
import unittest
from pathlib import Path

from fam_os.product.agent_model_scorecard import (
    AgentModelEvaluation,
    SCORECARD_VERSION,
    load_scorecard,
    select_measured_model,
)


class AgentModelScorecardTests(unittest.TestCase):
    def test_measured_completion_rate_wins_over_static_model_preference(self):
        evaluations = (
            AgentModelEvaluation("devstral-small-2:latest", 7, 8, 8.0, "2026-08-25T10:00:00Z"),
            AgentModelEvaluation("qwen3.8:27b", 8, 8, 12.0, "2026-08-25T10:00:00Z"),
        )
        self.assertEqual(
            "qwen3.8:27b",
            select_measured_model(
                ("devstral-small-2:latest", "qwen3.8:27b"), evaluations,
            ),
        )

    def test_incomplete_scorecard_cannot_route_production_agent(self):
        evaluation = AgentModelEvaluation(
            "qwen3.8:27b", 1, 1, 1.0, "2026-08-25T10:00:00Z",
        )
        self.assertIsNone(select_measured_model(("qwen3.8:27b",), (evaluation,)))

    def test_equally_reliable_execution_model_is_selected_by_latency(self):
        evaluations = (
            AgentModelEvaluation(
                "qwen3.8:27b", 8, 8, 25.6, "2026-08-25T10:00:00Z",
            ),
            AgentModelEvaluation(
                "nemotron-3.5-lightning:latest", 8, 8, 8.2,
                "2026-08-25T10:00:00Z",
            ),
        )

        self.assertEqual(
            "nemotron-3.5-lightning:latest",
            select_measured_model(
                ("qwen3.8:27b", "nemotron-3.5-lightning:latest"),
                evaluations,
            ),
        )

    def test_loads_only_versioned_valid_records(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "scorecard.json"
            path.write_text(json.dumps({
                "version": SCORECARD_VERSION,
                "models": [{
                    "model_ref": "qwen3.8:27b", "passed_cases": 8,
                    "total_cases": 8, "median_seconds": 12.5,
                    "evaluated_at": "2026-08-25T10:00:00Z",
                }, {"broken": True}],
            }), "utf-8")
            self.assertEqual("qwen3.8:27b", load_scorecard(path)[0].model_ref)


if __name__ == "__main__":
    unittest.main()
