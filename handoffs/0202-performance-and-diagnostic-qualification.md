# Handoff 0202: Performance and diagnostic qualification

**Date:** 2026-07-19  
**Plan step:** Phase 27.11  
**Status:** Partial  
**Previous handoff:** `0201-bounded-runtime-diagnostic-adapter.md`

## Objective

Make performance-regression evidence numerical and baseline-bound, and prevent
Phase 27.11 qualification from passing while any diagnostic kind lacks real
positive and negative evidence.

## Scope completed

- Bound performance requests to a baseline artifact digest, positive integer
  microunit value, and maximum regression in integer parts per million.
- Added strict POSIX-time parsing with exactly one `real` metric, decimal
  conversion, and integer-only regression computation.
- Physically ran a candidate benchmark through signed `/usr/bin/time`, systemd,
  and Bubblewrap. A generous baseline passed and a one-microunit baseline failed.
- Added per-kind qualification and complete-matrix contracts. A passing matrix
  requires every diagnostic kind exactly once, physical positive and negative
  receipts, and one release identity for installed proof.
- Changed diagnostic placeholder resolution to an exact `/workspace/` target
  after lexical candidate-path validation.

## Explicitly not completed

- Positive and negative physical qualification for gdb, core dump, strace,
  perf, time-memory, ThreadSanitizer, and LeakSanitizer.
- Signed installed matrix, production Core composition, and Console/Shell
  control for diagnostics.

## Architecture and decisions

ADR 0175 is extended without changing its boundary: performance measurements
are evidence only when tied to an exact baseline artifact and value. A short or
partial tool list cannot instantiate the complete qualification matrix.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/core/engineering/diagnostics.py` | Baseline value and failed-run comparison semantics |
| `src/fam_os/core/engineering/diagnostic_policy.py` | Exact sandbox target resolution |
| `src/fam_os/core/engineering/diagnostic_qualification.py` | Per-kind and aggregate qualification |
| `src/fam_os/core/engineering/__init__.py` | Qualification exports |
| `src/fam_os/adapters/bubblewrap/diagnostics.py` | POSIX metric parsing and regression policy |
| `src/fam_os/adapters/bubblewrap/engineering.py` | Read-only `/bin` bind for declared interpreters |
| `src/fam_os/adapters/bubblewrap/__init__.py` | Metric parser export |
| `src/fam_os/schemas/catalog.py` | Qualification schema roots |
| `tests/contract/schema_diagnostics_fixtures.py` | Baseline-bound request fixture |
| `tests/contract/schema_diagnostic_qualification_fixtures.py` | Complete qualification fixture |
| `tests/contract/test_schema_roundtrip.py` | New root roundtrips |
| `tests/contract/test_schema_compatibility.py` | Strict unknown/future rejection |
| `tests/unit/test_runtime_diagnostics.py` | Parser and fail-closed matrix tests |
| `tests/integration/test_runtime_diagnostics_exit.py` | Real pass/fail baseline fixture |
| `MASTER_PLANv2.md` | Phase 27.11 evidence update |

## Public interfaces

`PosixTimeMetricParser`, `RuntimeDiagnosticQualification`, and
`RuntimeDiagnosticQualificationMatrix`; request schemas add
`baseline_value_microunits`. Two new schema roots are
`fam.core.runtime-diagnostic-qualification/v1alpha1` and
`fam.core.runtime-diagnostic-matrix/v1alpha1`.

## Validation

```bash
PYTHONPATH=src:. .verification-venv/bin/python -m unittest tests.integration.test_runtime_diagnostics_exit tests.unit.test_runtime_diagnostics tests.contract.test_schema_roundtrip tests.contract.test_schema_compatibility -v
PYTHONPATH=src:. .verification-venv/bin/python tools/render_contract_schemas.py --check --output schemas
PYTHONPATH=src:. .verification-venv/bin/python -m compileall -q src/fam_os/core/engineering src/fam_os/adapters/bubblewrap tests/unit/test_runtime_diagnostics.py tests/integration/test_runtime_diagnostics_exit.py tests/contract
larry run "PYTHONPATH=src:. .verification-venv/bin/python -m unittest tests.integration.test_polyglot_engineering_sandbox tests.unit.test_engineering_execution -q"
git diff --check
```

Result: 39 tests passed, including real below-threshold and above-threshold
performance outcomes; 349 schemas validated; compileall and diff checks passed.

The first aggregate test run failed with `NameError` because the test omitted
the `ToolQualificationStatus` import. The missing test dependency was added;
production policy was unchanged, and the full focused run then passed.

Host feasibility probes found that the sandbox lacked a read-only `/bin` bind,
preventing gdb and script-based tools from invoking `/bin/sh`; the adapter was
corrected. They also confirmed `perf_event_paranoid=4` denies unprivileged perf
events, so CPU perf qualification remains unavailable pending a distinct
owner-authorized host-policy decision.

After the `/bin` correction, 16 diagnostic unit/physical tests and 10 existing
engineering-execution unit tests passed. Larry's bounded polyglot run returned
without an error tail, preserving the existing real-toolchain matrix.

## Evidence and artifacts

- `tests/integration/test_runtime_diagnostics_exit.py`
- `schemas/v1alpha1/fam.core.runtime-diagnostic-qualification.schema.json`
- `schemas/v1alpha1/fam.core.runtime-diagnostic-matrix.schema.json`
- `docs/decisions/0175-runtime-diagnostics-are-signed-bounded-and-sanitized.md`

## Known limitations and risks

- Wall-clock timing is noisy; release qualification needs repeated samples and
  hardware/profile identity, not one fixture.
- The current request binds a verified baseline value by contract, but the
  production baseline artifact reader/verifier is not yet composed.
- Tool presence does not prove ptrace, perf-event, sanitizer, or dump policy is
  usable under the installed sandbox.

## Operational notes

No service or host policy was changed. Physical tests use the existing user
systemd manager and Bubblewrap namespace path.

## Recommended next entry point

Build the per-kind qualification runner. Preserve unavailable and failed host
tool results, add regression fixtures for each parser, and do not instantiate a
passing matrix until all eight kinds pass on both required profiles.
