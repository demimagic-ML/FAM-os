import unittest

from fam_os.verification import (
    IsolationLevel,
    SandboxResult,
    SandboxStatus,
    VerificationRequest,
    VerificationStatus,
)
from fam_os.verification.python import PythonVerifier, TrustedPythonTests
from fam_os.verification.python.script import PASS_SENTINEL


TESTS = TrustedPythonTests("answer.v1", "assert answer(1) == 2")
CANDIDATE = "def answer(value):\n    return value + 1\n"


class FakeSandbox:
    def __init__(self, result: SandboxResult) -> None:
        self.result = result
        self.requests = []

    def run(self, request):
        self.requests.append(request)
        return self.result


def _clock():
    values = iter((10.0, 10.25))
    return lambda: next(values)


class PythonVerifierTests(unittest.TestCase):
    def test_maps_passing_sandbox_result(self) -> None:
        sandbox = FakeSandbox(SandboxResult(
            SandboxStatus.COMPLETED, IsolationLevel.BUBBLEWRAP, 0.1,
            stdout=f"{PASS_SENTINEL}\n", exit_code=0,
        ))
        report = PythonVerifier(sandbox, TESTS, clock=_clock()).verify(
            VerificationRequest("verification-1", CANDIDATE)
        )
        self.assertEqual(report.status, VerificationStatus.PASSED)
        self.assertEqual(report.evidence.isolation, "bubblewrap")
        self.assertIn("assert answer", sandbox.requests[0].script)

    def test_preserves_bounded_failure_evidence(self) -> None:
        sandbox = FakeSandbox(SandboxResult(
            SandboxStatus.COMPLETED, IsolationLevel.BUBBLEWRAP, 0.1,
            stderr="stable branch order", exit_code=1,
        ))
        report = PythonVerifier(sandbox, TESTS, clock=_clock()).verify(
            VerificationRequest("verification-2", CANDIDATE)
        )
        self.assertEqual(report.status, VerificationStatus.FAILED)
        self.assertEqual(report.stage, "tests")
        self.assertEqual(report.failure_details(), "stable branch order")

    def test_maps_timeout_to_candidate_failure(self) -> None:
        result = SandboxResult(
            SandboxStatus.TIMED_OUT, IsolationLevel.BUBBLEWRAP, 5.0,
            reason="sandbox exceeded limit",
        )
        report = PythonVerifier(FakeSandbox(result), TESTS, clock=_clock()).verify(
            VerificationRequest("verification-3", CANDIDATE)
        )
        self.assertEqual(report.status, VerificationStatus.FAILED)
        self.assertEqual(report.stage, "execution")

    def test_maps_missing_isolation_to_verifier_error(self) -> None:
        result = SandboxResult(
            SandboxStatus.UNAVAILABLE, IsolationLevel.NONE, 0,
            reason="Bubblewrap is required",
        )
        report = PythonVerifier(FakeSandbox(result), TESTS, clock=_clock()).verify(
            VerificationRequest("verification-4", CANDIDATE)
        )
        self.assertEqual(report.status, VerificationStatus.ERROR)

    def test_validation_failure_never_reaches_sandbox(self) -> None:
        sandbox = FakeSandbox(SandboxResult(
            SandboxStatus.COMPLETED, IsolationLevel.BUBBLEWRAP, 0.1, exit_code=0,
        ))
        report = PythonVerifier(sandbox, TESTS, clock=_clock()).verify(
            VerificationRequest(
                "verification-5", "import os\ndef answer():\n    return 1"
            )
        )
        self.assertEqual(report.stage, "validation")
        self.assertIsNone(report.evidence)
        self.assertEqual(sandbox.requests, [])


if __name__ == "__main__":
    unittest.main()
