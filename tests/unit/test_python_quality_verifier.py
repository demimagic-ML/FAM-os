import unittest

from fam_os.verification import IsolationLevel, SandboxResult, SandboxStatus, VerificationRequest
from fam_os.verification.python import (
    AnalyzerResult, PythonQualityVerifier, PythonVerifier, QualityGateStatus,
    TrustedPythonTests,
)
from fam_os.verification.python.script import PASS_SENTINEL


class FakeSandbox:
    def run(self, request):
        return SandboxResult(
            SandboxStatus.COMPLETED, IsolationLevel.BUBBLEWRAP, 0.1,
            stdout=PASS_SENTINEL, exit_code=0,
        )


class FakeAnalyzer:
    def __init__(self, analyzer_id, status=QualityGateStatus.PASSED):
        self.result = AnalyzerResult(analyzer_id, status, 0, "ok")

    def analyze(self, source):
        return self.result


class PythonQualityVerifierTests(unittest.TestCase):
    def verifier(self):
        units = PythonVerifier(FakeSandbox(), TrustedPythonTests("tests", "assert add(1, 2) == 3"))
        return PythonQualityVerifier(units, FakeAnalyzer("mypy"), FakeAnalyzer("ruff"))

    def test_all_four_independent_gates_are_required(self) -> None:
        report = self.verifier().verify(VerificationRequest(
            "quality-1", "def add(left: int, right: int) -> int:\n    return left + right\n"
        ))
        self.assertTrue(report.passed)
        self.assertEqual("python.syntax", report.syntax.analyzer_id)
        self.assertEqual("python.unit-tests", report.unit_tests.analyzer_id)

    def test_syntax_failure_blocks_every_later_gate(self) -> None:
        report = self.verifier().verify(VerificationRequest("quality-2", "def broken(: pass"))
        self.assertFalse(report.passed)
        self.assertEqual(QualityGateStatus.FAILED, report.syntax.status)
        self.assertEqual(QualityGateStatus.ERROR, report.typing.status)

    def test_one_analyzer_failure_withholds_combined_pass(self) -> None:
        units = PythonVerifier(FakeSandbox(), TrustedPythonTests("tests", "assert add(1, 2) == 3"))
        verifier = PythonQualityVerifier(
            units, FakeAnalyzer("mypy", QualityGateStatus.FAILED), FakeAnalyzer("ruff")
        )
        report = verifier.verify(VerificationRequest(
            "quality-3", "def add(left: int, right: int) -> int:\n    return left + right\n"
        ))
        self.assertFalse(report.passed)


if __name__ == "__main__":
    unittest.main()
