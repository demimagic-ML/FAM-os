# Verified mathematics experts

Phase 9.5 separates fluent reasoning from mathematical authority.

- `expert.math.llama3.2-reasoning` explains a problem and proposes an expression and answer. Its contract permanently sets `advisory_only=true`.
- `expert.math.deterministic-solvers-v1` evaluates integer/rational arithmetic with Python `Fraction` and solves safe-AST real symbolic equations with SymPy.
- The existing SymPy verifier remains available for symbolic equivalence and high-precision numerical sampling of generated expressions.

Only `MathSolverResult(verified=true)` can be released. The exact arithmetic parser permits integer constants, unary minus, and explicitly allowed binary operations. The symbolic solver permits the same safe expression grammar as the verifier and exactly one equality. Calls, attributes, imports, arbitrary names, and unsupported constructs are rejected without evaluation.

## Live evidence

```bash
PYTHONPATH=src python3 tools/run_math_expert_benchmark.py \
  --fixture tests/fixtures/math_experts/workstation-v1.json \
  --output artifacts/expert_fabric/phase9.5/math-expert-workstation.json
```

The benchmark deliberately preserves the model’s proposal alongside the authoritative result. Pass/fail derives only from the deterministic solver’s exact result, so a fluent proposal can never override deterministic mathematics.
