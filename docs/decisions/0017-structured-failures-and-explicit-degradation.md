# ADR 0017: Structured failures and explicit degradation

**Status:** Accepted  
**Date:** 2026-07-16

## Context

Phase 1 uses component-specific exception classes, verification statuses, application result statuses, and plain reason/error strings. Final execution copied some caught exception text directly into `TaskResult.reason`. That cannot safely support application connectors, multiple providers, retries, fallbacks, user-visible remediation, or stable serialized APIs.

Failure and degradation also have different meanings. A fallback or smaller context may still produce useful output with disclosed impact, while denial, failed verification, or an unavailable required capability can require withholding.

## Decision

Core owns a versioned `FailureEnvelope` and `DegradationNotice` family. Failures carry stable namespaced codes, categories, component ownership, bounded safe messages, explicit retry disposition, optional capability identity, and trusted evidence references. Degradations additionally carry kind, impact, continuation disposition, and original/replacement capability identity.

Application Fabric owns a smaller versioned `ApplicationFailure` with the same safety properties and status/category alignment. Application contracts do not import Core contracts; Phase 4 will translate component evidence into a final envelope.

Final `TaskResult` requires structured failure on failed results, forbids failure on success, requires evidence linkage, and prevents withholding degradations from accompanying released content. Final reason text must match the chosen safe message.

The existing verified-code use case maps known generation, placement, configuration, verification, and unsupported-route outcomes to stable structured records. It no longer copies caught exception text into final user-facing results.

## Consequences

- User-visible failures no longer depend on provider exception wording.
- Retry behavior, permission remediation, fallback disclosure, and withholding are explicit data.
- Raw evidence can remain restricted while final results retain auditable references.
- Application status semantics remain component-owned and dependency direction stays intact.
- Degraded successful results can be represented without falsely claiming equivalence.
- Phase 2.7 must serialize codes and define compatibility/unknown-code handling.
- Phase 4 must map every component failure and degradation through lifecycle state transitions.
- Telemetry and audit storage must retain restricted details without exposing them through safe messages.

## Alternatives considered

1. Continue using strings: rejected because strings cannot safely express retry, ownership, evidence, or degradation policy.
2. Put provider exceptions in the envelope: rejected because they can leak secrets, paths, payloads, or unstable implementation detail.
3. Make Application Fabric import Core failures: rejected because the dependency direction would reverse.
4. Treat every fallback as a failure: rejected because some lower-fidelity paths are useful when impact is visible and policy permits continuation.
5. Treat every degradation as successful: rejected because high-impact or required-capability loss can require confirmation or withholding.
6. Store raw diagnostic dictionaries in final results: rejected because they are unversioned and unsafe by default.

## Evidence

- `docs/protocols/FAILURE_DEGRADATION_CONTRACTS.md` documents the boundary and invariants.
- `tests/unit/test_failure_degradation_contracts.py` covers safe messages, categories, retries, evidence linkage, fallbacks, impact, and final-result policy.
- Application contract tests cover status/category matching and rejection of multiline raw details.
- Verified-code execution tests cover structured verification failure, unsupported-route degradation, and sanitized generation failure.
