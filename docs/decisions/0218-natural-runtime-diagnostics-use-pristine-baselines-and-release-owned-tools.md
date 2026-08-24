# ADR 0218: Natural runtime diagnostics use pristine baselines and release-owned tools

Status: Accepted

## Context

Phase 27.11 already had strict requests, receipts, signed recipes, sandbox
execution, sanitization, and real positive/negative tool fixtures. Those
components were not reachable from the natural engineering lifecycle. The
diagnostic helper was also referenced at a sandbox path that no installed
release owned, and performance comparison accepted an externally supplied
baseline value rather than capturing the exact pre-edit candidate.

## Decision

Core deterministically selects diagnostic kinds from durable natural intent
and repository file facts. A caller cannot provide recipe coordinates. Every
request now binds the task grant, principal, transport session, candidate or
post-apply phase, and one release-admitted signed recipe. Core authorizes the
request before persisting intent and again immediately before execution. The
receipt binds the live authorization decision, and immutable owner-encrypted
SQLite evidence is included in the same changeset checkpoint as ordinary
verifier evidence.

Performance work captures a signed, sandboxed baseline on the pristine
candidate before generation or editing. The sanitized measurement artifact,
integer microunit value, natural-intent regression threshold, target path,
candidate identity, recipe digest, and authorization are then reused for the
candidate and post-apply comparisons. An unavailable or zero-valued capture
cannot become a baseline.

Diagnostic helper code is packaged as a release expert asset. Its signed mount
uses a release-relative source kind, exact tree digest, and fixed sandbox
destination. The sandbox resolves it only beneath the verified active release;
host-absolute mounts retain their existing semantics. Stack, trace, crash, and
performance recipes use the helper to support exact Python targets as well as
native executables without a shell.

Diagnostic-only requests run against an isolated candidate and never mutate
the owner workspace. Modifying requests run selected diagnostics before the
changeset checkpoint and repeat them against a fresh post-apply clone before
commit. Console and Shell expose read-only request and receipt evidence; they
receive no recipe-selection or execution authority.

## Consequences

- Runtime diagnostics are part of the ordinary natural lifecycle rather than
  a parallel component API.
- Retries reconcile immutable requests and receipts without repeating a
  completed diagnostic or charging its budget twice.
- Performance regression is compared with the exact pre-edit run instead of a
  prompt-asserted number.
- Installed helper reachability is release-owned and digest checked.
- Local process-tree tracing is composed. Distributed service tracing remains
  a separate open Phase 27.11/27.13 composition gate and is not represented as
  local `strace` evidence.
- Source composition does not qualify an installed release or either hardware
  profile; those gates remain open.

## Alternatives considered

- Let the model choose recipes and arguments: rejected because model output is
  untrusted and cannot grant execution authority.
- Treat a user-written baseline number as exact evidence: rejected because it
  does not prove the pre-edit executable, recipe, profile, or measurement.
- Mount the builder checkout's helper in production: rejected because an
  installed release must not depend on builder paths or mutable source files.
- Call local process tracing “distributed tracing”: rejected because it would
  overstate the evidence and hide the service-environment work still required.

## Evidence

- `src/fam_os/core/engineering/runtime_diagnostic_intent.py`
- `src/fam_os/core/engineering/runtime_diagnostic_service.py`
- `src/fam_os/product/runtime_diagnostic_api.py`
- `src/fam_os/product/natural_engineering_execution.py`
- `src/fam_os/adapters/sqlite/engineering_runtime_diagnostic.py`
- `src/fam_os/adapters/bubblewrap/diagnostics.py`
- `src/fam_os/product/release_assembly.py`
- `tests/integration/test_natural_runtime_diagnostics.py`
- `tests/integration/test_runtime_diagnostics_exit.py`
- `tests/unit/test_runtime_diagnostic_composition.py`

