import unittest

from fam_os.experts.math_experts import (
    DeterministicMathSolver, MathReasoningAdvice, MathSolverKind, MathSolverRequest,
)


class MathExpertTests(unittest.TestCase):
    def test_exact_arithmetic_preserves_rational_result(self):
        result = DeterministicMathSolver().solve(MathSolverRequest(
            "arithmetic", MathSolverKind.EXACT_ARITHMETIC, "17 * 23 + 5 / 2",
        ))
        self.assertEqual("787/2", result.exact_result)
        self.assertTrue(result.verified)

    def test_symbolic_equation_solves_through_safe_ast(self):
        result = DeterministicMathSolver().solve(MathSolverRequest(
            "equation", MathSolverKind.SYMBOLIC_EQUATION, "2*x + 3 = 11", "x",
        ))
        self.assertEqual("4", result.exact_result)

    def test_unsafe_arithmetic_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unsupported construct"):
            DeterministicMathSolver().solve(MathSolverRequest(
                "unsafe", MathSolverKind.EXACT_ARITHMETIC, "__import__('os')",
            ))

    def test_reasoning_cannot_claim_authority(self):
        with self.assertRaisesRegex(ValueError, "cannot have authority"):
            MathReasoningAdvice("p", "why", "1+1", "2", "model", False)


if __name__ == "__main__":
    unittest.main()
