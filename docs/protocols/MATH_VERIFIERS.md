# Symbolic and numerical math verifiers

Math acceptance requires both symbolic equivalence and bounded numerical checks.
Expressions are converted from a strict Python AST allowlist into SymPy objects;
SymPy string evaluation is never used. Requests declare one real variable,
decimal sample points, absolute tolerance, and at least 16 precision digits.

Reports retain symbolic outcome, sample count, precision, maximum absolute error,
and the last observed counterexample. `passed` is the conjunction of symbolic and
numerical results. The canonical SymPy 1.14 run uses 80 digits, proves a polynomial
identity, and rejects `sin(x) == x` with a concrete counterexample.
