# Handoff 0127: Final integration rebaseline

**Date:** 2026-07-17  
**Plan step:** Phase 16  
**Status:** Complete  
**Previous handoff:** `0126-phase15-installed-operational-exit.md`

## Objective

Restore truthful whole-product status and make the difference between component
evidence and installed behavior enforceable before final integration continues.

## Scope completed

- Added `NEXT_STEPS.md` as the detailed Phase 16–23 gap-closure plan.
- Preserved Phases 0–15 and changed overall status to integration incomplete.
- Added a strict public integration-coverage contract and 19-subsystem manifest.
- Registered and rendered schema artifact 167.
- Added coverage completeness and anti-overstatement tests.
- Prevented production roots from importing acceptance or phase-exit builders.
- Defined bounded composition ownership for storage, Core, runtimes,
  applications, memory, Console, remote fabric, and factory.
- Declared mathematics, development, hardware, and training dependency profiles
  while retaining compatibility with `math-verification`.
- Documented clean test profile commands and made the optional SymPy equation
  test skip truthfully in the Base environment.

## Explicitly not completed

- No acceptance-only fabric was promoted into the installed service.
- Durable storage, managed Ollama, unified Core, live applications, memory,
  physical peers, and real adapter training remain Phases 17–22.
- Clean wheel matrices and 24-hour qualification remain Phase 23.

## Architecture and decisions

ADR 0111 introduces five explicit maturity levels. Final completion requires
every subsystem to be operationally proven from the installed release. Empty
composition placeholders were deliberately not created; each bounded unit is
introduced with its real implementation phase.

## Files changed

| Path | Purpose |
|---|---|
| `NEXT_STEPS.md` | Controlling final integration plan |
| `MASTER_PLAN.md` | Truthful status and Phase 16–23 sequence |
| `configs/integration/coverage.json` | Machine-readable maturity baseline |
| `src/fam_os/product/integration_coverage.py` | Typed coverage contract and loader |
| `schemas/v1alpha1/fam.product.integration-coverage.schema.json` | Generated public schema |
| `docs/architecture/FINAL_INTEGRATION_COMPOSITION.md` | Bounded production composition ownership |
| `docs/operations/TEST_PROFILES.md` | Clean dependency and test matrix |
| `docs/decisions/0111-final-integration-requires-production-reachability.md` | Reachability decision |
| `tests/contract/test_integration_coverage.py` | Coverage gates |
| `tests/architecture/test_product_composition_boundary.py` | Production import boundary |

## Public interfaces

- Schema: `fam.product.integration-coverage/v1alpha1`
- Configuration: `configs/integration/coverage.json`
- Optional dependency selectors: `mathematics`, `development`, `hardware`,
  `training`; existing `verification`, `math-verification`, and `media` remain.

## Validation

```bash
PYTHONPATH=src:. python3.12 -m unittest discover -s tests
PYTHONPATH=src:. python3.12 tools/render_contract_schemas.py --check
.verification-venv/bin/ruff check src/fam_os/product/integration_coverage.py tests/contract/test_integration_coverage.py tests/architecture/test_product_composition_boundary.py tests/unit/test_math_experts.py
PYTHONPATH=src:. .verification-venv/bin/mypy src/fam_os/product/integration_coverage.py
python3.12 -m json.tool configs/integration/coverage.json
git diff --check
```

Result: 845 tests passed with seven declared environment skips; 167 schemas
validated; lint, typing, JSON syntax, and whitespace checks passed.

## Evidence and artifacts

- `configs/integration/coverage.json`
- `schemas/v1alpha1/fam.product.integration-coverage.schema.json`
- `docs/decisions/0111-final-integration-requires-production-reachability.md`

## Known limitations and risks

- Most fabrics remain component-tested or acceptance-only and cannot yet be
  reached from the installed product.
- Profile selectors are declared, but Phase 23 must prove clean built-release
  matrices rather than relying on the current source environment.
- No independent human security review has occurred.

## Operational notes

This phase changes source governance and schemas only; it does not alter the
currently running `fam-os.service` or its data.

## Recommended next entry point

Begin Phase 17.1 by reading this handoff, ADR 0111, the Core lifecycle stores,
user isolation, recovery mode, and current installer. Implement the owner-private
SQLite WAL migration layer before replacing any volatile repository.
