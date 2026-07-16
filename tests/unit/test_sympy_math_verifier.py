import unittest

try:
    import sympy  # noqa: F401
except ImportError:
    sympy = None

from fam_os.verification import MathVerificationRequest
from fam_os.verification.math_sympy import SympyMathVerifier


@unittest.skipIf(sympy is None, "SymPy verification extra unavailable")
class SympyMathVerifierTests(unittest.TestCase):
    def test_symbolic_identity_and_high_precision_samples_pass(self) -> None:
        report = SympyMathVerifier().verify(MathVerificationRequest(
            "math-1", "(x + 1)**2", "x**2 + 2*x + 1", "x",
            ("-2", "0", "1.25"), "1e-40", 60,
        ))
        self.assertTrue(report.passed)
        self.assertEqual("0.0", report.maximum_absolute_error)

    def test_near_but_wrong_expression_emits_counterexample(self) -> None:
        report = SympyMathVerifier().verify(MathVerificationRequest(
            "math-2", "sin(x)", "x", "x", ("0", "0.5"), "1e-20", 50,
        ))
        self.assertFalse(report.passed)
        self.assertEqual("0.5", report.counterexample_point)

    def test_unsafe_expression_is_rejected_without_evaluation(self) -> None:
        with self.assertRaises(ValueError):
            SympyMathVerifier().verify(MathVerificationRequest(
                "math-3", "__import__('os')", "x", "x", ("1",), "1e-9",
            ))


if __name__ == "__main__":
    unittest.main()
