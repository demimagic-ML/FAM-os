"""Safe-AST SymPy symbolic and high-precision numerical verifier."""

import ast
from dataclasses import dataclass

from fam_os.verification.math_contracts import MathVerificationReport, MathVerificationRequest


@dataclass(frozen=True, slots=True)
class SympyMathVerifier:
    def verify(self, request: MathVerificationRequest) -> MathVerificationReport:
        import sympy

        symbol = sympy.Symbol(request.variable, real=True)
        candidate = _parse(request.candidate_expression, symbol, sympy)
        reference = _parse(request.reference_expression, symbol, sympy)
        symbolic = sympy.simplify(candidate - reference) == 0
        tolerance = sympy.Float(request.absolute_tolerance, request.precision_digits)
        maximum, counterexample, numerical = sympy.Float(0), None, True
        for point_text in request.sample_points:
            point = sympy.Float(point_text, request.precision_digits)
            error = abs(sympy.N(candidate.subs(symbol, point) - reference.subs(symbol, point), request.precision_digits))
            if not error.is_finite or error > tolerance:
                numerical, counterexample = False, point_text
            if error.is_finite and error > maximum:
                maximum = error
        return MathVerificationReport(
            request.verification_id, bool(symbolic), numerical, str(maximum),
            counterexample, request.precision_digits, len(request.sample_points),
            bool(symbolic and numerical),
        )


def _parse(source, symbol, sympy):
    node = ast.parse(source, mode="eval").body
    return _convert(node, symbol, sympy)


def _convert(node, symbol, sympy):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return sympy.Rational(str(node.value))
    if isinstance(node, ast.Name) and node.id == str(symbol):
        return symbol
    if isinstance(node, ast.BinOp) and type(node.op) in _OPERATORS:
        return _OPERATORS[type(node.op)](_convert(node.left, symbol, sympy), _convert(node.right, symbol, sympy))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_convert(node.operand, symbol, sympy)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _FUNCTIONS and len(node.args) == 1:
        return getattr(sympy, node.func.id)(_convert(node.args[0], symbol, sympy))
    raise ValueError("math expression contains an unsupported construct")


_OPERATORS = {
    ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b, ast.Div: lambda a, b: a / b,
    ast.Pow: lambda a, b: a**b,
}
_FUNCTIONS = frozenset({"sin", "cos", "tan", "exp", "log", "sqrt", "Abs"})
