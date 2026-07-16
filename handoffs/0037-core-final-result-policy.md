# Handoff 0037: Registry-backed terminal result policy

**Date:** 2026-07-16  
**Plan step:** Phase 4.8  
**Status:** Complete  
**Previous handoff:** `0036-core-control-transitions.md`

## Objective

Create safe `TaskResult` values only from terminal plan state and trusted linked
evidence, never from caller-provided or failed candidate content.

## Scope completed

- Added candidate, acceptance, and degradation evidence registry contracts.
- Added release-candidate and verification-pass event references.
- Required exact request/plan candidate binding.
- Required passing cross-linked acceptance covering release predecessor checks.
- Withheld blocking degradation even at a release terminal.
- Mapped cancellation, timeout, expiry, withhold, and fail to content-free safe
  structured results.
- Excluded failed/repair/escalation references from user-facing terminal evidence.

## Explicitly not completed

- Durable evidence storage or real verifier/provider population.
- Cross-process final-result transport.
- Phase 4 end-to-end lifecycle matrix.

## Architecture and decisions

ADR 0038 makes a terminal necessary but insufficient for release. Trusted
registry evidence owns content; the assembly call cannot supply it. Verification
must link to that exact candidate and declared acceptance IDs.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/core/lifecycle/final_contracts.py` | Trusted evidence and assembly outcomes. |
| `src/fam_os/core/lifecycle/final_ports.py` | Replaceable evidence registry port. |
| `src/fam_os/core/lifecycle/final_registry.py` | In-memory fake registry. |
| `src/fam_os/core/lifecycle/final_service.py` | Terminal release/withhold/fail policy. |
| `src/fam_os/core/lifecycle/contracts.py` | Release and verification reference kinds. |
| `tests/unit/test_core_final_result_policy.py` | Release and withholding proofs. |
| `tests/architecture/test_core_final_result_boundary.py` | Provider-boundary guard. |
| `docs/protocols/CORE_FINAL_RESULT_POLICY.md` | Policy documentation. |
| `docs/decisions/0038-registry-backed-terminal-release.md` | Durable decision. |
| `README.md`, `src/fam_os/core/README.md`, `MASTER_PLAN.md` | Status updates. |

## Public interfaces

- Added candidate/acceptance evidence records and `FinalEvidenceRegistry`.
- Added `InMemoryFinalEvidenceRegistry` and `FinalResultPolicy.assemble`.
- Added `RELEASE_CANDIDATE` and `VERIFICATION_PASS` evidence kinds.

## Validation

```bash
PYTHONPATH=src python3 -m unittest tests.unit.test_core_final_result_policy tests.architecture.test_core_final_result_boundary
PYTHONPATH=src python3 -m unittest discover -s tests
PYTHONPATH=src:. python3 tools/render_contract_schemas.py --check
PYTHONPATH=src python3 -m compileall -q src tests tools
larry index . && larry health .
```

Result: 8 focused tests and 399 full-suite tests passed; 35 schemas matched;
compile and AST gates passed; Larry indexed 544 files / 1,509 symbols; graph has
7,679 nodes / 25,942 edges; health is clean.

## Known limitations and risks

- Evidence registry is process-local.
- Result rejection codes are internal Python outcomes, not serialized roots.
- Real trusted verifier linkage remains future integration work.

## Operational notes

No services, models, applications, or machine configuration changed.

## Recommended next entry point

Begin Phase 4.9 with a fake-driven end-to-end matrix from admitted/routed request
through terminal result. Cover release and every safe non-release branch plus
replay, expiry, budget, and failed-content invariants.
