# Handoff 0030: Core request admission and permission context

**Date:** 2026-07-16  
**Plan step:** Phase 4.1 request admission and permission context  
**Status:** Complete  
**Previous handoff:** `0029-supervisor-threat-model.md`

## Objective

Prevent unauthenticated, expired, over-scoped, malformed, or replayed requests
from reaching routing while keeping Core admission deterministic, least privilege,
prompt-private on failure, and independent of every runtime/external adapter.

## Scope completed

- Added strict immutable request identity, authority grant, effective permission,
  admitted request, and admission outcome contracts.
- Resolved opaque authority references through an injected trusted registry;
  callers cannot pass arbitrary grant objects to the admission service.
- Bound authority to exact principal and session without putting identity inside
  caller-authored `TaskRequest` content.
- Required aware issue/expiry/revocation times and mandatory finite authority
  lifetime; future, expired, and revoked grants fail.
- Required complete capability coverage and attached only the request's authorized
  capabilities to the effective permission context.
- Made missing authority and identity mismatch intentionally indistinguishable.
- Added an atomic locked replay registry and reserved IDs only after all authority
  checks passed.
- Returned existing structured Core failures with fixed safe prompt-free messages.
- Tightened task request ID, contract version, prompt length/NUL, capability count,
  capability identity, and uniqueness invariants.
- Added an architecture guard prohibiting runtime/application/Supervisor imports
  from the admission package.
- Added protocol documentation, ADR 0031, and this handoff.

## Explicitly not completed

- No router, model, application connector, verifier, Scheduler, or Supervisor is
  called by admission.
- The in-memory authority and replay registries are not crash-durable.
- Registry insertion is trusted; cryptographic credential verification and the
  authenticated local transport remain Phase 5.2 work.
- Deadlines, cancellation, approval state, and permission expiry during execution
  remain later Phase 4 steps.
- Admission contracts are not yet serialized roots; they remain internal until a
  transport boundary requires canonical encoding.

## Architecture and decisions

ADR 0031 chooses trusted registry lookup over caller-supplied grants. The input
identity carries only principal, session, and opaque authority reference. The
registry grant is the trusted binding and has a mandatory expiry.

Effective permission is exact least privilege: its capability tuple must equal
the admitted request's requirements, not the full authority grant. Replay
reservation occurs after permission validation so an invalid caller cannot burn
a legitimate request ID. The locked in-memory implementation admits exactly one
concurrent reservation.

Malformed typed requests fail at construction/strict decoding; valid typed but
unauthorized requests return a `FailureEnvelope`. Neither path invokes routing.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/core/admission/contracts.py` | Identity, authority, permission, outcome evidence |
| `src/fam_os/core/admission/ports.py` | Authority and replay registry ports |
| `src/fam_os/core/admission/registry.py` | In-memory trusted authority and atomic replay state |
| `src/fam_os/core/admission/service.py` | Deterministic admission workflow |
| `src/fam_os/core/admission/__init__.py` | Admission public API |
| `src/fam_os/core/contracts/request.py` | Bounded strict TaskRequest invariants |
| `tests/unit/test_request_admission.py` | Admission, denial, replay, concurrency tests |
| `tests/architecture/test_core_admission_boundary.py` | Runtime-import prohibition |
| `docs/protocols/CORE_REQUEST_ADMISSION.md` | Protocol and failure behavior |
| `docs/decisions/0031-trusted-registry-core-request-admission.md` | Admission decision |

## Public interfaces

- `RequestIdentity`
- `RequestAuthorityGrant`
- `RequestPermissionContext`
- `AdmittedTaskRequest`
- `RequestAdmissionOutcome`
- `RequestAuthorityRegistry`
- `RequestReplayRegistry`
- `InMemoryRequestAuthorityRegistry`
- `InMemoryRequestReplayRegistry`
- `RequestAdmissionService.admit(...)`

## Validation

```bash
PYTHONPATH=src:. python3 -m unittest \
  tests.unit.test_request_admission \
  tests.unit.test_core_contracts \
  tests.contract.test_schema_roundtrip \
  tests.contract.test_schema_compatibility \
  tests.contract.test_cross_contract_references
```

Result: all 39 focused admission/core/schema tests passed in 0.121 seconds.

```bash
PYTHONPATH=src:. python3 -m unittest discover -s tests
PYTHONPATH=src:. python3 tools/render_contract_schemas.py --check
python3 -m compileall -q src tools tests
```

Result: all 343 tests passed in 0.263 seconds, all 35 generated schemas matched,
and compilation completed successfully. Phase 3 closed with 333 tests.

An AST audit found no `src/` or `tools/` module at or above 300 lines and no
function at or above 50 lines.

Larry refreshed 483 files and verified clean. The codebase graph refreshed in
fast mode with 7,128 nodes and 22,104 edges.

## Known limitations and risks

- Authority/replay state is lost on process restart.
- Trusted registry population has no production credential adapter yet.
- Request IDs are globally single-use in the current registry, not namespaced by
  principal; this favors collision safety and requires globally unique IDs.
- A denial does not reserve its request ID by design; transport rate limiting is
  still required against repeated invalid attempts.
- Permission expiry is checked at admission only; Phase 4.5 must recheck it at
  approval/action transitions.
- Prompt size is character-bounded, not token-budgeted; Scheduler/Core planning
  will own token/resource budgeting later.

## Recommended next entry point

Begin Phase 4.2 with an admitted request, never a raw `TaskRequest`. Define a
provider-neutral routing use case that passes only request identity, prompt, and
effective required capabilities to the existing Router port; require returned
request identity and capability coverage to match; reject widening, missing,
invalid, or unavailable route evidence as structured Core failures; and keep the
permission context attached for the next plan state.
