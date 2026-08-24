# Handoff 0201: Bounded runtime diagnostic adapter

**Date:** 2026-07-19  
**Plan step:** Phase 27.11  
**Status:** Partial  
**Previous handoff:** `0200-engineering-completion-rebaseline.md`

## Objective

Move runtime diagnostics from strict contracts into signed release policy and
a real contained execution path without introducing arbitrary command
arguments or secret-bearing evidence.

## Scope completed

- Added eight distinct signed diagnostic recipe purposes and release-owned
  specifications for stack, dump, trace, CPU/memory profile, race/leak, and
  performance workflows.
- Bound each diagnostic request to an immutable recipe coordinate and payload,
  exact purpose, network mode, environment keys, and one normalized
  candidate-relative target placeholder.
- Added a concrete systemd/Bubblewrap adapter using the existing cgroup,
  namespace, rlimit, output, time, and process-tree launcher.
- Added deterministic secret-pattern redaction and mode-0600, O_EXCL,
  O_NOFOLLOW candidate artifact storage with digest evidence.
- Ran real Python fixtures through systemd and Bubblewrap. Normal execution
  persisted sanitized evidence; output flooding produced no artifact.
- Added a regression fix that walks lexical target components before resolving
  them, so final and parent symlinks cannot disappear during admission.

## Explicitly not completed

- Real positive and deliberately failing runs for gdb core capture, strace,
  perf, time, ThreadSanitizer, LeakSanitizer, and baseline comparison.
- Process interruption/restart reconciliation and installed product
  composition for diagnostics.
- Phase 27.11 and its installed exit evidence.

## Architecture and decisions

ADR 0175 remains authoritative. A diagnostic recipe accepts exactly one typed
target path; it is not a raw-shell substitute. Diagnostic output becomes
evidence only after deterministic sanitization and bounded candidate storage.
Privileged host-process attachment remains a separate host-admin authority.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/core/engineering/execution.py` | Exact diagnostic recipe purposes |
| `src/fam_os/core/engineering/diagnostics.py` | Version-bound request/receipt contracts |
| `src/fam_os/core/engineering/diagnostic_policy.py` | Recipe admission and target resolution |
| `src/fam_os/core/engineering/production_recipes.py` | Eight release-owned specifications |
| `src/fam_os/adapters/bubblewrap/engineering.py` | Typed resolved-argv support |
| `src/fam_os/adapters/bubblewrap/diagnostics.py` | Execution, sanitization, and artifact adapter |
| `src/fam_os/adapters/bubblewrap/__init__.py` | Public adapter exports |
| `tests/unit/test_runtime_diagnostics.py` | Policy and injected-adapter tests |
| `tests/integration/test_runtime_diagnostics_exit.py` | Real contained execution fixtures |
| `MASTER_PLANv2.md` | Phase 27.11 partial evidence |

## Public interfaces

`BubblewrapRuntimeDiagnosticAdapter`, `CandidateDiagnosticArtifactStore`,
`DeterministicDiagnosticTextSanitizer`,
`diagnostic_recipe_specifications`, and
`RuntimeDiagnosticRecipePolicy.resolve_argv`. `ToolRecipePurpose` adds eight
diagnostic values. Runtime diagnostic request and receipt schemas now bind the
signed recipe version.

## Validation

```bash
PYTHONPATH=src:. .verification-venv/bin/python -m unittest tests.integration.test_runtime_diagnostics_exit tests.unit.test_runtime_diagnostics tests.contract.test_schema_roundtrip tests.contract.test_schema_compatibility -v
PYTHONPATH=src:. .verification-venv/bin/python tools/render_contract_schemas.py --check --output schemas
PYTHONPATH=src:. .verification-venv/bin/python -m compileall -q src/fam_os/core/engineering src/fam_os/adapters/bubblewrap tests/unit/test_runtime_diagnostics.py tests/integration/test_runtime_diagnostics_exit.py
git diff --check
```

Result: 36 tests passed, including three real systemd/Bubblewrap fixtures; 347
schemas validated; compileall and diff checks passed. The adapter files remain
below the 300-line target.

The first symlink fixture failed because the adapter resolved the target before
calling `is_symlink()`. The fixed implementation walks each lexical component
before resolution, and the regression fixture now passes.

## Evidence and artifacts

- `tests/integration/test_runtime_diagnostics_exit.py`
- `docs/decisions/0175-runtime-diagnostics-are-signed-bounded-and-sanitized.md`
- `MASTER_PLANv2.md`

## Known limitations and risks

- Recipe presence is not tool qualification. Several host tools can be absent
  or restricted by kernel policy and must fail unavailable, not pass by
  declaration.
- Pattern redaction is intentionally conservative but cannot prove arbitrary
  binary dumps secret-free; binary dump export needs a separate scanner.
- Candidate diagnostic evidence is not yet reachable through installed Core,
  Console, or Shell.

## Operational notes

Real tests require `python3`, `bwrap`, and `systemd-run`; they skip rather than
claim a pass when those tools are unavailable.

## Recommended next entry point

Add per-kind positive/negative qualification with truthful unavailable states,
starting with gdb/strace/time and compiler sanitizers. Then add performance
baseline parsing and interruption cleanup before production composition.
