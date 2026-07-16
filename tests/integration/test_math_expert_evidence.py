import json
import unittest
from pathlib import Path

from fam_os.experts.math_evidence import MathBenchmarkCaseResult, MathExpertEvidence
from fam_os.experts.math_experts import MathReasoningAdvice, MathSolverKind, MathSolverResult

ROOT = Path(__file__).parents[2]


class MathExpertEvidenceTests(unittest.TestCase):
    def test_live_reasoning_is_advisory_and_solver_is_authoritative(self):
        raw = json.loads((
            ROOT / "artifacts/expert_fabric/phase9.5/math-expert-workstation.json"
        ).read_text())
        cases = tuple(_case(value) for value in raw.pop("cases"))
        evidence = MathExpertEvidence(cases=cases, **raw)

        self.assertTrue(evidence.passed)
        self.assertTrue(all(case.reasoning.advisory_only for case in cases))
        self.assertEqual(("787/2", "4"), tuple(case.solver.exact_result for case in cases))
        self.assertEqual("4", cases[1].solver.exact_result)


def _case(raw):
    advice_raw, solver_raw = raw.pop("reasoning"), raw.pop("solver")
    advice = MathReasoningAdvice(**advice_raw)
    solver_raw["kind"] = MathSolverKind(solver_raw["kind"])
    solver = MathSolverResult(**solver_raw)
    return MathBenchmarkCaseResult(reasoning=advice, solver=solver, **raw)


if __name__ == "__main__":
    unittest.main()
