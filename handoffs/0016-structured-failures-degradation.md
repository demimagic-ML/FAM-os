# Handoff 0016: Structured failures and explicit degradation

**Date:** 2026-07-16  
**Plan step:** Phase 2.6  
**Status:** Complete  
**Previous handoff:** `0015-component-manifest-contracts.md`

## Objective

Replace ambiguous final error strings with safe, versioned, component-owned failure records and represent useful-but-reduced execution as explicit degradation rather than silently claiming equivalence.

## Scope completed

- Added the Core-owned `fam.failure/v1alpha1` contract family.
- Added stable failure categories, component ownership, retry disposition, bounded safe messages, evidence references, and optional capability identity.
- Added explicit degradation kind, impact, continuation policy, and original/replacement capability identity.
- Extended `TaskResult` with structured failure and degradation collections.
- Required failed results to carry a failure, prohibited successful results from carrying failures, and linked all final evidence references.
- Prevented successful content release when a degradation requires withholding.
- Added the Application Fabric-owned `fam.application.failure/v1alpha1` family without reversing the Application-to-Core dependency boundary.
- Replaced Application observation/action error strings with `ApplicationFailure` and enforced status/category alignment.
- Mapped verified-code generation, placement, configuration, verification, and unsupported-route outcomes to safe structured records.
- Removed caught exception text from final user-visible results.
- Split terminal-result construction out of the execution use case after a size audit found that the first integrated draft exceeded the module target.
- Added focused tests, protocol documentation, ADR 0017, ownership documentation, and plan/status updates.

## Explicitly not completed

- No JSON encoder, decoder, schema document, unknown-field rule, or version migration was added; that is Phase 2.7.
- No global error-code registry or compatibility policy was created.
- No raw exception telemetry or restricted diagnostic store was added.
- No retry executor, fallback selector, user-confirmation UI, or lifecycle state machine was implemented.
- No routing, scheduler, supervisor, verifier, registry, or memory-specific adapter was changed to emit the Core envelope directly.
- No connector process, MCP transport, VS Code extension, or external application action was introduced.

## Architecture and decisions

ADR 0017 separates failure from degradation. Failure records explain why an intended operation did not produce releasable output. Degradation records explain how an operation continued with reduced capability, fidelity, context, or verification.

Core and Application Fabric keep separate public contracts. Application observations and actions retain their own status vocabulary and use `ApplicationFailure`; a later orchestration boundary translates component evidence into `FailureEnvelope`. This preserves dependency direction and prevents Core policy from leaking into connector implementations.

Messages in public failure records are bounded, single-line, and explicitly safe for display. Stable codes and trusted evidence references carry identity; raw provider exceptions, command output, paths, connector payloads, and secrets remain outside the contract.

The first verified-execution integration grew `core/execution/use_case.py` to 326 lines. Terminal-result mapping and configuration errors were separated into focused modules. The final use-case module is 241 lines and `terminal_results.py` is 111 lines.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/core/contracts/failures.py` | Core failure and degradation contract family |
| `src/fam_os/core/contracts/result.py` | Final result failure, degradation, evidence, and release invariants |
| `src/fam_os/core/contracts/__init__.py` | Public Core failure/degradation exports |
| `src/fam_os/applications/failures.py` | Application-owned structured failure family |
| `src/fam_os/applications/observations.py` | Structured observation errors and status/category checks |
| `src/fam_os/applications/actions.py` | Structured action errors and status/category checks |
| `src/fam_os/applications/__init__.py` | Public Application failure exports |
| `src/fam_os/core/execution/errors.py` | Execution configuration exception boundary |
| `src/fam_os/core/execution/terminal_results.py` | Safe mapping from terminal execution outcomes to final results |
| `src/fam_os/core/execution/use_case.py` | Integration of structured terminal results without raw exception exposure |
| `tests/unit/test_failure_degradation_contracts.py` | Failure, retry, degradation, withholding, and evidence invariants |
| `tests/unit/test_application_permissions_actions.py` | Application action structured-error coverage |
| `tests/unit/test_application_connector_contracts.py` | Observation and fake-connector structured-error coverage |
| `tests/unit/test_verified_code_execution.py` | Verified-execution failure/degradation mapping coverage |
| `docs/protocols/FAILURE_DEGRADATION_CONTRACTS.md` | Public failure and degradation protocol reference |
| `docs/protocols/CORE_CONTRACTS.md` | Core result-contract update |
| `docs/protocols/APPLICATION_CONTRACTS.md` | Application failure-contract update |
| `docs/decisions/0017-structured-failures-and-explicit-degradation.md` | Architecture decision |
| `src/fam_os/core/README.md` | Core ownership update |
| `src/fam_os/applications/README.md` | Application ownership update |
| `MASTER_PLAN.md` | Phase 2.6 completion evidence and Phase 2.7 entry point |
| `README.md` | Current implementation and next-step status |
| `handoffs/README.md` | Handoff sequence entry |
| `handoffs/0016-structured-failures-degradation.md` | This implementation record |

## Public interfaces

- `FAILURE_CONTRACT_VERSION`
- `FailureCategory`
- `FailureComponent`
- `RetryDisposition`
- `DegradationKind`
- `DegradationImpact`
- `DegradationDisposition`
- `FailureEnvelope`
- `DegradationNotice`
- `APPLICATION_FAILURE_CONTRACT_VERSION`
- `ApplicationFailureCategory`
- `ApplicationRetryDisposition`
- `ApplicationFailure`
- `TaskResult.failure`
- `TaskResult.degradations`

## Validation

```bash
cd <REPO_ROOT>/FAM_OS
PYTHONPATH=src:. python3 -m unittest \
  tests.unit.test_failure_degradation_contracts \
  tests.unit.test_application_permissions_actions \
  tests.unit.test_application_connector_contracts \
  tests.unit.test_verified_code_execution
```

Result: all 38 focused tests passed in 0.002 seconds; 0 failures.

```bash
PYTHONPATH=src:. python3 -m unittest discover -s tests
```

Result: all 193 FAM_OS tests passed in 0.039 seconds; 0 failures. The previous suite contained 176 tests.

```bash
python3 -m compileall -q src tools tests
```

Result: completed successfully.

```bash
rg -n "Ollama|ollama|systemd|subprocess|Traceback|str\(exc\)" \
  src/fam_os/core/contracts/failures.py \
  src/fam_os/applications/failures.py \
  src/fam_os/core/contracts/result.py \
  src/fam_os/core/execution/terminal_results.py
```

Result: no provider, service-manager, process, traceback, or caught-exception-text dependency was found in the public failure/result boundary.

```bash
find src/fam_os -name '*.py' -type f -print0 | xargs -0 wc -l | sort -nr | head -12
```

Result: the largest implementation module is `core/execution/use_case.py` at 241 lines. All implementation modules remain below the 300-line target.

## Evidence and artifacts

- `docs/protocols/FAILURE_DEGRADATION_CONTRACTS.md`
- `docs/decisions/0017-structured-failures-and-explicit-degradation.md`
- `tests/unit/test_failure_degradation_contracts.py`
- `tests/unit/test_application_permissions_actions.py`
- `tests/unit/test_application_connector_contracts.py`
- `tests/unit/test_verified_code_execution.py`
- Provider-neutral boundary: `docs/decisions/0002-provider-neutral-contract-boundaries.md`
- Application boundary: `docs/decisions/0013-application-fabric-python-contracts.md`

## Known limitations and risks

- Contract identifiers are Python version markers until Phase 2.7 defines serialized compatibility.
- Consumers have no declared policy for unknown fields, unknown enum values, or unknown error codes.
- The safe-message shape rejects multiline and oversized detail but cannot prove semantic absence of secrets; trusted classifiers must construct it.
- Raw exceptions are sanitized from final results but are not yet retained in restricted telemetry linked to the evidence reference.
- Component-specific mapping is complete only for current Application Fabric results and the verified-code execution path.
- Retry disposition is descriptive; no retry budget, backoff, or idempotency executor consumes it yet.
- Degradation impact is qualitative and has no benchmark-backed quality threshold yet.
- Phase 4 still must route failures and degradations through lifecycle transitions, permission decisions, and result release policy.

## Operational notes

This change is immutable Python contracts, in-memory mapping, documentation, and tests only. It started no provider or connector, performed no external action, persisted no diagnostics, and changed no machine service.

## Recommended next entry point

Begin Phase 2.7. Read this handoff, the four Phase 2 contract protocol documents, and their owning Python modules. Define a small serialization/schema registry with explicit version matching, unknown-field policy, stable enum/code handling, and compatibility tests. Keep serialization separate from domain dataclasses and do not introduce provider-specific fields.
