"""Shell projections preserve engineering result truth states."""

import unittest
from dataclasses import replace

from fam_os.core.engineering import EngineeringExecutionAssurance

from fam_os.shell import render_engineering_result
from tests.contract.schema_engineering_fixtures import (
    engineering_grant_schema_values,
    engineering_result_schema_values,
)


class ShellEngineeringProjectionTests(unittest.TestCase):
    def test_each_result_kind_has_an_unambiguous_terminal_label(self) -> None:
        proposal, receipt, publication, published, unavailable = (
            engineering_result_schema_values()
        )
        expected = (
            "proposed; no workspace mutation is claimed",
            "independently verified workspace mutation",
            "publication proposed; nothing external is claimed published",
            "publication observed and postcondition-verified",
            "capability unavailable; no effect is claimed",
        )
        for value, statement in zip(
            (proposal, receipt, publication, published, unavailable),
            expected,
            strict=True,
        ):
            with self.subTest(result_kind=value.result_kind.value):
                rendered = render_engineering_result(value)
                self.assertIn(value.result_kind.value, rendered)
                self.assertIn(statement, rendered)

    def test_projection_does_not_render_model_supplied_proposal_summary(self) -> None:
        proposal = engineering_result_schema_values()[0]
        self.assertNotIn(proposal.summary, render_engineering_result(proposal))

    def test_execution_assurance_is_rendered_without_elevation(self) -> None:
        execution = engineering_grant_schema_values()[-1]
        unverified = replace(
            execution,
            assurance=EngineeringExecutionAssurance.EXECUTED_UNVERIFIED,
            verifier_run_ids=(),
        )
        waived = replace(
            execution,
            assurance=EngineeringExecutionAssurance.VERIFICATION_WAIVED,
            verifier_run_ids=(),
            waiver_decision_id="waiver-1",
        )
        self.assertIn("State: verified", render_engineering_result(execution))
        self.assertIn("State: executed_unverified", render_engineering_result(unverified))
        self.assertIn("State: verification_waived", render_engineering_result(waived))


if __name__ == "__main__":
    unittest.main()
