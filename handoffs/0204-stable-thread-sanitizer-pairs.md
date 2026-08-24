# Handoff 0204: Stable ThreadSanitizer pairs

**Date:** 2026-07-19  
**Plan step:** Phase 27.11  
**Status:** Partial  
**Previous handoff:** `0203-physical-diagnostic-toolchain.md`

## Objective

Replace intermittent ThreadSanitizer unavailability with a stable real
clean-pass and race-detected pair without weakening sandbox limits.

## Scope completed

- Confirmed `/usr/bin/setarch x86_64 -R` is permitted both on the host and
  inside the existing unprivileged Bubblewrap namespace.
- Changed only the ThreadSanitizer target launch to deterministic address
  layout; compile flags, systemd cgroup memory, swap denial, CPU, process, file,
  output, wall, and cleanup limits remain intact.
- Tightened the integration test from conditional unavailable acceptance back
  to mandatory clean pass and mandatory race failure containing a real
  ThreadSanitizer report.
- Repeated the physical pair ten consecutive times successfully.
- Reran the complete focused diagnostic/schema/sandbox suite.

## Explicitly not completed

- Installed toolchain packaging and per-kind installed qualification rows.
- Production Core, Console, and Shell composition.
- Both-profile and Phase 31 aggregate evidence.

## Architecture and decisions

No authority or resource boundary changed. `setarch -R` changes only the child
process address randomization needed by this signed diagnostic recipe; it does
not add capabilities, host attachment, network, or privilege.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/adapters/diagnostics/tool.py` | Deterministic ThreadSanitizer child launch |
| `tests/integration/test_runtime_diagnostics_exit.py` | Mandatory stable positive/negative pair |
| `MASTER_PLANv2.md` | Corrected Phase 27.11 physical evidence |
| `handoffs/0204-stable-thread-sanitizer-pairs.md` | Append-only correction to Handoff 0203 limitation |

## Public interfaces

None. The signed helper's internal race execution vector now includes
`/usr/bin/setarch x86_64 -R`.

## Validation

```bash
for attempt in 1 2 3 4 5 6 7 8 9 10; do PYTHONPATH=src:. .verification-venv/bin/python -m unittest tests.integration.test_runtime_diagnostics_exit.RuntimeDiagnosticsExitTests.test_thread_sanitizer_accepts_clean_and_rejects_race_fixture -q || exit 1; done
PYTHONPATH=src:. .verification-venv/bin/python -m unittest tests.integration.test_runtime_diagnostics_exit tests.unit.test_runtime_diagnostics tests.contract.test_schema_roundtrip tests.contract.test_schema_compatibility tests.unit.test_bubblewrap_commands tests.unit.test_bubblewrap_runner tests.unit.test_sandbox_process_capture -q
PYTHONPATH=src:. .verification-venv/bin/python tools/render_contract_schemas.py --check --output schemas
PYTHONPATH=src:. .verification-venv/bin/python -m compileall -q src/fam_os/adapters/diagnostics src/fam_os/adapters/bubblewrap src/fam_os/core/engineering tests/integration/test_runtime_diagnostics_exit.py tests/unit/test_runtime_diagnostics.py
git diff --check
```

Result: all ten repeated physical pairs passed; the focused suite passed 55
tests in 6.89 seconds; 349 schemas, compileall, and diff checks passed.

## Evidence and artifacts

- `tests/integration/test_runtime_diagnostics_exit.py`
- `MASTER_PLANv2.md`
- `handoffs/0203-physical-diagnostic-toolchain.md`

## Known limitations and risks

- Deterministic layout slightly changes a race fixture's address behavior; the
  actual concurrent access and ThreadSanitizer instrumentation remain real.
- These are source physical runs, not installed or both-profile evidence.

## Operational notes

No host sysctl, package, service, or policy was changed.

## Recommended next entry point

Package and sign the diagnostic helper into the installed candidate, emit all
eight positive/negative qualification rows, and compose diagnostics behind Core
authority before checking Phase 27.11.
