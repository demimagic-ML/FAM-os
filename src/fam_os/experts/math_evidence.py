"""Evidence contract for advisory reasoning and deterministic math solvers."""

from dataclasses import dataclass

from fam_os.experts.math_experts import MathReasoningAdvice, MathSolverResult

MATH_EVIDENCE_CONTRACT_VERSION = "fam.expert.math-evidence/v1alpha1"


@dataclass(frozen=True, slots=True)
class MathBenchmarkCaseResult:
    case_id: str
    reasoning: MathReasoningAdvice
    solver: MathSolverResult
    expected_exact_result: str
    passed: bool

    def __post_init__(self) -> None:
        expected = self.solver.verified and self.solver.exact_result == self.expected_exact_result
        if self.passed != expected:
            raise ValueError("math case pass must derive from deterministic solver")


@dataclass(frozen=True, slots=True)
class MathExpertEvidence:
    evidence_id: str
    reasoning_expert_id: str
    reasoning_artifact_sha256: str
    solver_expert_id: str
    solver_artifact_sha256: str
    cases: tuple[MathBenchmarkCaseResult, ...]
    passed: bool
    contract_version: str = MATH_EVIDENCE_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if not self.cases or self.passed != all(case.passed for case in self.cases):
            raise ValueError("math evidence pass must match all cases")
        for value in (self.reasoning_artifact_sha256, self.solver_artifact_sha256):
            if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
                raise ValueError("math evidence digests must be lowercase SHA-256")
