# Handoff 0203: Physical diagnostic toolchain

**Date:** 2026-07-19  
**Plan step:** Phase 27.11  
**Status:** Partial  
**Previous handoff:** `0202-performance-and-diagnostic-qualification.md`

## Objective

Physically execute crash, trace, profile, race, and leak recipes with useful
sanitized artifacts rather than treating recipe presence as proof.

## Scope completed

- Added a signed, read-only mounted, stdlib-only helper that invokes exact
  subprocess vectors without a shell.
- Kept raw cores in sandbox tmpfs, analyzed them with gdb, removed them before
  exit, and exported only sanitized text evidence.
- Compiled and ran exact C targets under LeakSanitizer and ThreadSanitizer with
  bounded output, time, process trees, transient files, and cgroup memory.
- Separated retained evidence bytes from transient compilation bytes.
- Added an explicit debug/dump/sanitizer virtual-address exception while
  preserving resident `MemoryMax` and every other limit.
- Replaced blocked perf-event CPU profiling with unprivileged Python cProfile.
- Passed real positive/negative pairs for core dumps, stack traces, strace, CPU
  profiles, memory profiles, LeakSanitizer, and performance regression.
- Redacted secret-shaped output and host build paths.
- Preserved ThreadSanitizer's intermittent `unexpected memory mapping` as
  unavailable rather than a pass or a race finding.

## Explicitly not completed

- Stable physical ThreadSanitizer qualification or an installed alternative.
- The complete eight-kind qualification matrix.
- Signed installed evidence and Core/Console/Shell composition.

## Architecture and decisions

ADR 0176 distinguishes sparse virtual address reservations from resident cgroup
memory and transient linker files from retained evidence. The exception is
kind-restricted and does not widen shell, network, secret, or host authority.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/adapters/diagnostics/tool.py` | Ephemeral core and sanitizer helper |
| `src/fam_os/core/engineering/production_recipes.py` | Viable release recipes |
| `src/fam_os/core/engineering/diagnostics.py` | Transient bytes and address-space policy |
| `src/fam_os/adapters/bubblewrap/diagnostics.py` | Limit separation and sanitization |
| `src/fam_os/verification/sandbox/contracts.py` | Virtual-address policy |
| `src/fam_os/adapters/bubblewrap/rlimits.py` | Conditional `RLIMIT_AS` |
| `tests/integration/test_runtime_diagnostics_exit.py` | Real per-kind pairs |
| `docs/decisions/0176-sanitizer-virtual-address-space-is-separated-from-resident-memory.md` | Resource decision |
| `MASTER_PLANv2.md` | Phase evidence |

## Public interfaces

`RuntimeDiagnosticLimits.temporary_file_bytes`,
`RuntimeDiagnosticLimits.unbounded_virtual_address_space`, and
`SandboxLimits.unbounded_virtual_address_space`. Defaults retain bounded
address space; only admitted debug/dump/sanitizer requests may omit
`RLIMIT_AS` while remaining cgroup-memory bounded.

## Validation

```bash
PYTHONPATH=src:. .verification-venv/bin/python -m unittest tests.integration.test_runtime_diagnostics_exit tests.unit.test_runtime_diagnostics tests.contract.test_schema_roundtrip tests.contract.test_schema_compatibility tests.unit.test_bubblewrap_commands tests.unit.test_bubblewrap_runner tests.unit.test_sandbox_process_capture -v
PYTHONPATH=src:. .verification-venv/bin/python tools/render_contract_schemas.py --check --output schemas
PYTHONPATH=src:. .verification-venv/bin/python -m compileall -q src/fam_os/core/engineering src/fam_os/adapters/diagnostics src/fam_os/adapters/bubblewrap tests/unit/test_runtime_diagnostics.py tests/integration/test_runtime_diagnostics_exit.py tests/contract
git diff --check
```

Result: 55 tests passed, 349 schemas validated, compileall
passed, and `git diff --check` reported no errors.

## Failed experiments preserved

- A shared 4 KiB file/evidence limit killed `ld`; limits are now separate.
- LeakSanitizer failed reserving shadow memory under `RLIMIT_AS`; resident
  cgroup memory is now separated from sparse virtual address space.
- ThreadSanitizer alternates between real execution and `unexpected memory
  mapping` on this kernel; this remains unavailable and blocks its row.
- gdb initially failed under `RLIMIT_AS`; the exact debug-only exception fixed
  core analysis while keeping `MemoryMax`.
- cProfile was shadowed by `profile.py`, `/usr/bin/time` tried to execute a
  non-executable script, and gdb exposed a host build path. Fixtures and
  sanitization were corrected without weakening acceptance.

## Evidence and artifacts

- `tests/integration/test_runtime_diagnostics_exit.py`
- `docs/decisions/0176-sanitizer-virtual-address-space-is-separated-from-resident-memory.md`
- `MASTER_PLANv2.md`

## Known limitations and risks

- ThreadSanitizer is not qualified on this kernel; the matrix must reject it.
- Text sanitization is not a binary core sanitizer. Raw core export is forbidden.
- Source physical tests are not installed-release evidence.

## Operational notes

No sysctl, package, service, or privileged policy changed. `perf` remains
blocked by `perf_event_paranoid=4`; cProfile is the unprivileged CPU tier.

## Recommended next entry point

Package the diagnostic helper in the signed installed candidate and emit all
per-kind qualification rows. Resolve ThreadSanitizer through a compatible
signed toolchain or leave the matrix failed; then compose behind Core authority.
