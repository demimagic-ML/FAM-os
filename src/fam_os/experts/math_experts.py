"""Advisory mathematical reasoning with deterministic solver authority."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction
from typing import Protocol

MATH_EXPERT_CONTRACT_VERSION = "fam.expert.math/v1alpha1"


class MathSolverKind(StrEnum):
    EXACT_ARITHMETIC = "exact_arithmetic"
    SYMBOLIC_EQUATION = "symbolic_equation"


@dataclass(frozen=True, slots=True)
class MathReasoningAdvice:
    problem_id: str
    explanation: str
    proposed_expression: str
    proposed_answer: str
    model_ref: str
    advisory_only: bool = True
    contract_version: str = MATH_EXPERT_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if not self.advisory_only:
            raise ValueError("mathematical model reasoning cannot have authority")
        if not all(value.strip() for value in (
            self.problem_id, self.explanation, self.proposed_expression,
            self.proposed_answer, self.model_ref,
        )):
            raise ValueError("mathematical reasoning fields must not be empty")


@dataclass(frozen=True, slots=True)
class MathSolverRequest:
    problem_id: str
    kind: MathSolverKind
    expression: str
    variable: str | None = None
    contract_version: str = MATH_EXPERT_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if not self.problem_id.strip() or not self.expression.strip():
            raise ValueError("solver request fields must not be empty")
        if self.kind is MathSolverKind.SYMBOLIC_EQUATION and not self.variable:
            raise ValueError("symbolic equations require a variable")


@dataclass(frozen=True, slots=True)
class MathSolverResult:
    problem_id: str
    kind: MathSolverKind
    exact_result: str
    solver_id: str
    verified: bool
    contract_version: str = MATH_EXPERT_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if not self.exact_result.strip() or not self.solver_id.strip() or not self.verified:
            raise ValueError("only verified deterministic solver results may be released")


class MathReasoner(Protocol):
    def reason(self, problem_id: str, prompt: str) -> MathReasoningAdvice: ...


@dataclass(frozen=True, slots=True)
class DeterministicMathSolver:
    solver_id: str = "fam.math.deterministic/v1"

    def solve(self, request: MathSolverRequest) -> MathSolverResult:
        if request.kind is MathSolverKind.EXACT_ARITHMETIC:
            result = str(_evaluate_fraction(request.expression))
        else:
            result = _solve_equation(request.expression, request.variable or "")
        return MathSolverResult(
            request.problem_id, request.kind, result, self.solver_id, True,
        )


def _evaluate_fraction(source: str) -> Fraction:
    return _fraction_node(ast.parse(source, mode="eval").body)


def _fraction_node(node: ast.AST) -> Fraction:
    if isinstance(node, ast.Constant) and isinstance(node.value, int):
        return Fraction(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_fraction_node(node.operand)
    if isinstance(node, ast.BinOp) and type(node.op) in _FRACTION_OPERATORS:
        return _FRACTION_OPERATORS[type(node.op)](
            _fraction_node(node.left), _fraction_node(node.right),
        )
    raise ValueError("exact arithmetic expression contains an unsupported construct")


def _solve_equation(source: str, variable: str) -> str:
    if source.count("=") != 1 or not variable.isidentifier():
        raise ValueError("symbolic equation must contain one equality")
    import sympy  # type: ignore[import-untyped]
    from fam_os.verification.math_sympy import _parse

    symbol = sympy.Symbol(variable, real=True)
    left, right = (value.strip() for value in source.split("=", 1))
    solutions = sympy.solve(_parse(left, symbol, sympy) - _parse(right, symbol, sympy), symbol)
    if not solutions or any(value.has(sympy.I) for value in solutions):
        raise ValueError("symbolic equation has no supported real solution")
    return ",".join(str(value) for value in solutions)


_FRACTION_OPERATORS = {
    ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b, ast.Div: lambda a, b: a / b,
    ast.Pow: lambda a, b: a**b if b.denominator == 1 else _unsupported_power(),
}


def _unsupported_power():
    raise ValueError("exact powers require an integer exponent")
