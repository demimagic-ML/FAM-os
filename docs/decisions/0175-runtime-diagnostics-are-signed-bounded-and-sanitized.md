# ADR 0175: Runtime diagnostics are signed, bounded, and sanitized

Status: Accepted

## Context

Debuggers, dump collectors, tracers, profilers, and race or leak detectors can
observe sensitive memory, attach to unintended processes, produce unbounded
artifacts, or turn a diagnostic request into arbitrary execution. Performance
claims can also be manufactured if a run is compared with an unspecified
baseline.

## Decision

Runtime diagnostics remain unprivileged candidate execution. Every request
binds an admitted signed recipe and payload digest, exact candidate, diagnostic
kind, target arguments, sanitized environment keys, network policy, collection
limits, requested artifact kinds, and execute authority. Host process attach
or privileged dump access requires a separate future host-administration
changeset and is not implied by diagnostic authority.

Artifacts are bounded, digest-addressed, explicitly sanitized, and rejected if
they contain secret content. Performance regression uses an exact baseline
artifact digest, integer measurements, and an explicit threshold. Cross-
contract validation rejects substituted request identities, recipes,
baselines, artifact types, or over-limit evidence. A passing receipt requires a
zero exit and cannot exceed the performance threshold.

The existing Ed25519 `SignedToolRecipe` catalog is reused with eight distinct
diagnostic recipe purposes. Core requires an exact kind-to-purpose match and
rejects any request that widens the signed environment or network policy.
Performance baselines bind both a digest and an integer microunit value. The
adapter accepts exactly one POSIX `real` metric, uses decimal parsing and
integer regression arithmetic, and cannot pass above the request threshold.
Whole-diagnostics qualification is fail closed unless every kind has physical
positive and negative receipts; installed matrices bind all rows to one release.

## Consequences

- Diagnostic tools cannot inherit ambient home, credentials, network, or host
  process authority.
- Raw dumps may be collected inside the sandbox but cannot leave it as evidence
  until a deterministic sanitizer marks the resulting artifact secret-free.
- Each real debugger or profiler adapter must have signed recipes, positive and
  hostile fixtures, process-tree termination, and installed qualification.
- Component contracts alone do not make Phase 27.11 production-reachable.

## Evidence

- `src/fam_os/core/engineering/diagnostics.py`
- `tests/unit/test_runtime_diagnostics.py`
- `tests/contract/schema_diagnostics_fixtures.py`
- `schemas/v1alpha1/fam.core.runtime-diagnostic-request.schema.json`
- `schemas/v1alpha1/fam.core.runtime-diagnostic-receipt.schema.json`
