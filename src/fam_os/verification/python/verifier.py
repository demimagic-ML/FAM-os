"""Deterministic Python verifier composed over a sandbox port."""

from dataclasses import dataclass
from time import perf_counter
from typing import Callable

from fam_os.verification import (
    SandboxLimits,
    SandboxRequest,
    SandboxResult,
    SandboxRunner,
    SandboxStatus,
    VerificationEvidence,
    VerificationReport,
    VerificationRequest,
    VerificationStatus,
)
from fam_os.verification.python.bundles import TrustedPythonTests
from fam_os.verification.python.extraction import extract_python_candidate
from fam_os.verification.python.policy import sanitize_python_candidate
from fam_os.verification.python.script import PASS_SENTINEL, build_verification_script


PYTHON_VERIFIER_ID = "python.deterministic-tests.v1"


@dataclass(slots=True)
class PythonVerifier:
    sandbox: SandboxRunner
    tests: TrustedPythonTests
    limits: SandboxLimits = SandboxLimits()
    clock: Callable[[], float] = perf_counter

    def verify(self, request: VerificationRequest) -> VerificationReport:
        started = self.clock()
        try:
            extracted = extract_python_candidate(request.candidate)
            normalized = sanitize_python_candidate(extracted)
        except (SyntaxError, ValueError) as error:
            return self._validation_failure(request.verification_id, str(error), started)
        sandbox_request = SandboxRequest(
            build_verification_script(normalized, self.tests), self.limits
        )
        outcome = self.sandbox.run(sandbox_request)
        return self._execution_report(
            request.verification_id, normalized, outcome, started
        )

    def _validation_failure(
        self, verification_id: str, reason: str, started: float
    ) -> VerificationReport:
        return VerificationReport(
            verification_id=verification_id,
            verifier_id=PYTHON_VERIFIER_ID,
            status=VerificationStatus.FAILED,
            stage="validation",
            reason=reason,
            wall_seconds=self.clock() - started,
        )

    def _execution_report(
        self,
        verification_id: str,
        normalized: str,
        outcome: SandboxResult,
        started: float,
    ) -> VerificationReport:
        status, stage, reason = _verdict(outcome)
        evidence = VerificationEvidence(
            stdout=outcome.stdout,
            stderr=outcome.stderr,
            exit_code=outcome.exit_code,
            normalized_candidate=normalized,
            isolation=outcome.isolation.value,
        )
        return VerificationReport(
            verification_id=verification_id,
            verifier_id=PYTHON_VERIFIER_ID,
            status=status,
            stage=stage,
            reason=reason,
            wall_seconds=self.clock() - started,
            evidence=evidence,
        )


def _verdict(outcome: SandboxResult) -> tuple[VerificationStatus, str, str]:
    if outcome.status is SandboxStatus.UNAVAILABLE:
        return VerificationStatus.ERROR, "execution", outcome.reason
    if outcome.status is SandboxStatus.TIMED_OUT:
        return VerificationStatus.FAILED, "execution", outcome.reason
    passed = outcome.exit_code == 0 and PASS_SENTINEL in outcome.stdout
    if passed:
        return VerificationStatus.PASSED, "passed", "all deterministic tests passed"
    return VerificationStatus.FAILED, "tests", "deterministic tests failed"
