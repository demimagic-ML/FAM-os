# ADR 0010: Parent RNF retirement as read-only evidence

**Status:** Accepted  
**Date:** 2026-07-16

## Context

Phase 1 moved the parent RNF prototype's hardware discovery, inference runtime, systemd/cgroup control, verification, routing, activation, repair, escalation, release policy, tests, and measured experiments into modular FAM_OS boundaries. Phase 1.10 produced a passing machine parity report and preserved a diagnostic failure that improved runtime eviction semantics.

Keeping two active implementations after parity would create behavior drift, duplicate fixes, ambiguous ownership, and a path for new FAM_OS code to depend on prototype coupling.

## Decision

`FAM_OS/` is the canonical active implementation. The parent `rnf/` package and its associated configs, evaluations, scripts, tests, benchmark artifacts, handoff, and experiment documents are frozen as runnable historical evidence.

The freeze is repository policy, not Unix permission mutation. Historical commands and tests remain runnable. Parent changes require an explicit user request for historical maintenance and must not become dependencies of FAM_OS.

An architecture test parses every Python file under `FAM_OS/src` and `FAM_OS/tools` and rejects static or constant-string dynamic imports whose module root is `rnf`. Parent-versus-FAM tests may read or execute frozen evidence, but active implementation and tools cannot import it.

New runtime code, tests, tools, configuration, schemas, and documentation belong under `FAM_OS/`.

## Consequences

- There is one active product implementation and one runnable evidence base.
- New agents encounter the freeze through root `AGENTS.md`, the root README banner, and `PROTOTYPE_READ_ONLY.md`.
- FAM_OS cannot quietly regress into importing prototype god modules.
- Reproduction remains possible because no chmod or deletion was performed.
- Historical defects are not fixed opportunistically; migrated behavior is fixed in FAM_OS.
- Phase 2 begins from measured, provider-neutral boundaries rather than from parent code.

## Alternatives considered

1. Delete the prototype: rejected because raw reproduction and historical comparison remain valuable.
2. Apply filesystem read-only permissions: rejected because it would make normal testing, packaging caches, and explicit historical maintenance brittle.
3. Keep both implementations active: rejected because ownership and behavior would diverge.
4. Rely on documentation alone: rejected because an automated import boundary provides cheap continuous enforcement.
5. Reject parent imports only under `src`: rejected because benchmark tools could otherwise reintroduce prototype coupling.

## Evidence

- `artifacts/parity/phase1-parity-20260716-095056-252893.json` passed every Phase 1 parity gate.
- `docs/migration/PHASE_1_PARITY_REPORT.md` records test and measured comparisons.
- `tests/architecture/test_no_parent_imports.py` enforces the active-code boundary and marker.
- Root `AGENTS.md`, `README.md`, and `PROTOTYPE_READ_ONLY.md` identify FAM_OS as canonical.
- Handoff 0010 records final rediscovery, tests, and operational state.
