# ADR 0007: Trusted Python verifier and explicit sandbox isolation

**Status:** Accepted  
**Date:** 2026-07-16

## Context

The RNF prototype proves deterministic verification of generated Python, but one module mixes Markdown extraction, AST policy, trusted test loading, script assembly, Bubblewrap discovery, process limits, subprocess execution, verdict conversion, and JSON persistence. It also silently falls back to a process with resource limits when Bubblewrap is unavailable, even though that fallback does not provide equivalent filesystem and network isolation.

FAM_OS must preserve the verified stable-topological-sort behavior while keeping model output untrusted, verifier tests trusted, sandbox mechanics replaceable, and isolation claims precise.

## Decision

The verification component owns:

- Provider-neutral verification reports and bounded evidence.
- Provider-neutral sandbox requests, limits, outcomes, isolation levels, and the `SandboxRunner` port.
- Python candidate extraction and the trusted AST allow policy.
- Trusted Python test bundles, verification-script assembly, and verdict conversion.

Bubblewrap and Linux process limits are concrete adapter behavior under `adapters/bubblewrap`. The adapter runs Python with `-I -S`, a fixed minimal environment, a temporary root view, no host home bind, all Bubblewrap namespaces unshared, capabilities dropped, and CPU, address-space, file-size, descriptor, core-dump, returned-output, and wall-time limits.

Bubblewrap is required by default. If it is missing, the adapter returns `SandboxStatus.UNAVAILABLE` and the verifier returns `VerificationStatus.ERROR`. A process-limit-only fallback exists solely as an explicit setting and reports `IsolationLevel.PROCESS_LIMITS`; it is never presented as Bubblewrap isolation.

Candidate syntax or policy rejection, test failure, and timeout are candidate failures. Missing required isolation is a verifier error. Only exit code zero plus a verifier-owned pass sentinel produces `VerificationStatus.PASSED`.

The returned evidence is bounded and may contain stdout, stderr, exit code, normalized candidate, and the actual isolation level. Validation failures do not attach normalized candidate evidence. Trusted tests are constructed separately from candidate content and selected by the caller.

The AST policy preserves the prototype import allowlist and top-level-definition sanitation while also rejecting direct `__builtins__` access, dynamic `getattr`/`setattr`/`delattr`, dunder-string access, and decorators at every nesting level.

## Consequences

- Python verification can be tested with a fake sandbox and sandbox execution can be tested without verifier policy.
- Core orchestration will consume one stable report instead of Bubblewrap output or prototype dictionaries.
- Isolation downgrade is visible and opt-in.
- Candidate code cannot replace or edit verifier-owned tests through the verifier interface. A configured verifier implements the provider-neutral `VerificationRequest -> VerificationReport` port, so orchestration never receives the Python test bundle.
- The parent stable-toposort pass/fail behavior is preserved through live parity tests.
- Verification persistence and external report schemas remain separate Phase 2 and telemetry work.

## Security boundary

This Phase 1 sandbox is defense in depth, not a hardened hostile multi-tenant boundary. It does not yet provide a seccomp profile, signed verifier bundles, cgroup PID or I/O ceilings, parent-side streaming output enforcement, multi-user policy, kernel-exploit protection, or a complete proof that the Python AST allow policy has no escape. Bubblewrap and user namespaces depend on the host kernel configuration.

The subprocess API captures output before the adapter truncates returned evidence. CPU and wall limits bound execution time, but a future hardened launcher must enforce output limits while streaming so excessive pipe output cannot grow parent memory first.

## Alternatives considered

1. Copy `rnf/verifier.py`: rejected because it preserves a god module and silent isolation downgrade.
2. Put Bubblewrap command details in the Python verifier: rejected because candidate policy and operating-system isolation must be independently replaceable.
3. Treat process limits as equivalent to Bubblewrap: rejected because process limits do not hide the filesystem or unshare networking.
4. Allow model-supplied tests: rejected because a candidate could weaken its own acceptance policy.
5. Claim a production security boundary after parity: rejected because Phase 8.2 still requires hardening and adversarial security review.

## Evidence

- Unit tests preserve all five parent extraction and sandbox behaviors through the new boundaries and add adversarial candidate-policy, verdict-mapping, command-construction, and isolation-downgrade coverage.
- Live parity tests show that both parent and migrated verifiers accept the correct stable topological sort and reject the unstable branch-order implementation.
- Live sandbox tests show Bubblewrap isolation hides the user home, wall timeout terminates an infinite loop, and returned evidence is truncated to its configured bound.
- Handoff 0007 records exact commands, test counts, graph verification, limitations, and the next migration step.
