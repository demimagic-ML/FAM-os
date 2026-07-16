"""Strict symbolic and numerical acceptance contracts."""

from dataclasses import dataclass


MATH_VERIFICATION_CONTRACT_VERSION = "fam.verifier.math/v1alpha1"


@dataclass(frozen=True, slots=True)
class MathVerificationRequest:
    verification_id: str
    candidate_expression: str
    reference_expression: str
    variable: str
    sample_points: tuple[str, ...]
    absolute_tolerance: str
    precision_digits: int = 50
    contract_version: str = MATH_VERIFICATION_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if not all(value.strip() for value in (
            self.verification_id, self.candidate_expression,
            self.reference_expression, self.variable, self.absolute_tolerance,
        )):
            raise ValueError("math verification text fields must not be empty")
        if not self.sample_points or self.precision_digits < 16:
            raise ValueError("math verification requires samples and at least 16 digits")


@dataclass(frozen=True, slots=True)
class MathVerificationReport:
    verification_id: str
    symbolic_equivalent: bool
    numerical_passed: bool
    maximum_absolute_error: str
    counterexample_point: str | None
    precision_digits: int
    sample_count: int
    passed: bool
    contract_version: str = MATH_VERIFICATION_CONTRACT_VERSION
