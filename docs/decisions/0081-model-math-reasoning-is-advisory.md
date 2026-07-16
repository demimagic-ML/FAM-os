# ADR 0081: Model mathematics reasoning is advisory

- Status: accepted
- Date: 2026-07-16

## Decision

Generative mathematics reasoning may explain and propose, but it never supplies the authoritative result. Exact rational arithmetic and safe symbolic equation solvers produce releasable results. Generated identities remain subject to the independent symbolic and high-precision numerical verifier.

One bounded formatting repair is allowed for reasoning JSON. Repair does not alter the deterministic solver request, expected result, or verification rule.

## Consequences

- A plausible but numerically wrong explanation cannot become the FAM answer.
- Rational results do not silently lose precision through floating-point conversion.
- Solver inputs are intentionally narrower than unrestricted SymPy syntax.
- New solver kinds require new explicit grammar and evidence rather than widening evaluation implicitly.
