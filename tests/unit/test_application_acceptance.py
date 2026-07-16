import unittest

from fam_os.application_acceptance.contracts import (
    IntegrationLevel, OperationMeasurement, ScenarioEvidence,
)
from fam_os.application_acceptance.runner import _exit_gate, _summarize


class ApplicationAcceptanceContractTests(unittest.TestCase):
    def test_exit_gate_requires_all_levels_verified_work_and_reduced_success(self):
        full = tuple(
            scenario(f"full-{index}", level, verified=index == 0)
            for index, level in enumerate((
                IntegrationLevel.NATIVE, IntegrationLevel.MCP,
                IntegrationLevel.DETERMINISTIC,
            ))
        )
        combined = full + (scenario(
            "full-accessibility", IntegrationLevel.ACCESSIBILITY,
        ),)
        self.assertFalse(_exit_gate(combined))
        three = (
            ScenarioEvidence(
                "combined", True, True, False, "ok", ("cap",), (), (),
                tuple(item.measurements[0] for item in combined),
            ),
            scenario("test", IntegrationLevel.DETERMINISTIC),
            scenario("edit", IntegrationLevel.NATIVE, verified=True),
            scenario("reduced", IntegrationLevel.ACCESSIBILITY, reduced=True),
        )
        self.assertTrue(_exit_gate(three))

    def test_level_summary_reports_reliability_and_resource_totals(self):
        values = (
            scenario("one", IntegrationLevel.MCP),
            scenario("two", IntegrationLevel.MCP, succeeded=False),
        )
        summary = _summarize(values)[IntegrationLevel.MCP.value]
        self.assertEqual(2, summary["attempts"])
        self.assertEqual(1, summary["successes"])
        self.assertEqual(0.5, summary["success_rate"])
        self.assertEqual(20, summary["context_bytes_total"])


def scenario(
    identity, level, *, succeeded=True, verified=False, reduced=False,
):
    measurement = OperationMeasurement(
        f"operation-{identity}", level, "cap", succeeded, 1.0, 10, 2.0,
        3, 4, 100, 120, None if succeeded else "operation.failed",
    )
    return ScenarioEvidence(
        identity, succeeded, verified, reduced, "ok" if succeeded else "",
        ("cap",), (), (), (measurement,),
        failure_code=None if succeeded else "scenario.failed",
    )


if __name__ == "__main__":
    unittest.main()
