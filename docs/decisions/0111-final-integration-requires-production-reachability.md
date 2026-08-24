# ADR 0111: Final integration requires production reachability

Status: Accepted

## Context

Phases 0–15 produced substantial contracts, component tests, acceptance
harnesses, and a narrow installed Shell-to-Ollama path. Those forms of evidence
were previously summarized as whole-product completion even when the installed
daemon could not reach the Expert, Scheduler, Verification, Application, Memory,
Adaptation, Remote, or Factory fabrics.

## Decision

FAM_OS records subsystem maturity as `contract_only`, `component_tested`,
`acceptance_only`, `production_wired`, or `operationally_proven`. The canonical
state is the versioned `configs/integration/coverage.json` manifest.

Final completion requires every listed subsystem to be
`operationally_proven`, production-reachable, supported by installed evidence,
and free of an exit-gate gap. Acceptance and evidence generators cannot be
imported by the production composition root. Historical phase evidence remains
valid and append-only, but cannot be promoted implicitly to installed behavior.

## Consequences

- The program status returns to integration incomplete.
- Phases 16–23 close the gap without rewriting Phases 0–15.
- Every major phase updates the coverage manifest and creates a handoff.
- Product claims can be checked automatically against explicit installed
  evidence rather than inferred from artifact presence.

## Alternatives considered

- Treat the Phase 15 installed chat path as completion. Rejected because it
  proves only a narrow fixed-model interaction.
- Delete or rewrite historical exits. Rejected because it would erase useful
  evidence and break append-only governance.
- Use prose maturity only. Rejected because it is not enforceable.

## Evidence

- `NEXT_STEPS.md`
- `configs/integration/coverage.json`
- `tests/contract/test_integration_coverage.py`
- `tests/architecture/test_product_composition_boundary.py`
