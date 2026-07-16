"""Composable Python syntax, type, static-analysis, and unit-test gates."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from fam_os.verification import VerificationRequest, VerificationStatus
from fam_os.verification.python.policy import PythonSafetyVisitor
from fam_os.verification.python.verifier import PythonVerifier


PYTHON_QUALITY_CONTRACT_VERSION = "fam.verifier.python-quality/v1alpha1"


class QualityGateStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class AnalyzerResult:
    analyzer_id: str
    status: QualityGateStatus
    exit_code: int | None
    output: str


class PythonAnalyzer(Protocol):
    def analyze(self, source: str) -> AnalyzerResult: ...


@dataclass(frozen=True, slots=True)
class PythonQualityReport:
    verification_id: str
    syntax: AnalyzerResult
    unit_tests: AnalyzerResult
    typing: AnalyzerResult
    static_analysis: AnalyzerResult
    contract_version: str = PYTHON_QUALITY_CONTRACT_VERSION

    @property
    def passed(self) -> bool:
        return all(item.status is QualityGateStatus.PASSED for item in (
            self.syntax, self.unit_tests, self.typing, self.static_analysis,
        ))


@dataclass(slots=True)
class PythonQualityVerifier:
    unit_verifier: PythonVerifier
    type_analyzer: PythonAnalyzer
    static_analyzer: PythonAnalyzer

    def verify(self, request: VerificationRequest) -> PythonQualityReport:
        syntax = _syntax_gate(request.candidate)
        if syntax.status is not QualityGateStatus.PASSED:
            blocked = AnalyzerResult("not-run", QualityGateStatus.ERROR, None, "blocked by syntax")
            return PythonQualityReport(request.verification_id, syntax, blocked, blocked, blocked)
        unit = self.unit_verifier.verify(request)
        evidence = unit.evidence
        return PythonQualityReport(
            request.verification_id, syntax,
            AnalyzerResult("python.unit-tests", _map_status(unit.status), evidence.exit_code if evidence else None, unit.failure_details()),
            self.type_analyzer.analyze(request.candidate),
            self.static_analyzer.analyze(request.candidate),
        )


def _syntax_gate(source: str) -> AnalyzerResult:
    try:
        tree = ast.parse(source)
        PythonSafetyVisitor().visit(tree)
    except (SyntaxError, ValueError) as error:
        return AnalyzerResult("python.syntax", QualityGateStatus.FAILED, None, str(error))
    return AnalyzerResult("python.syntax", QualityGateStatus.PASSED, 0, "valid safe AST")


def _map_status(status: VerificationStatus) -> QualityGateStatus:
    return {
        VerificationStatus.PASSED: QualityGateStatus.PASSED,
        VerificationStatus.FAILED: QualityGateStatus.FAILED,
        VerificationStatus.ERROR: QualityGateStatus.ERROR,
    }[status]
