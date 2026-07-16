# ADR 0031: Admit Core requests through trusted authority and replay registries

**Status:** Accepted  
**Date:** 2026-07-16

## Context

`TaskRequest` previously carried intent and required capabilities but no runtime
permission binding. Passing a grant object supplied by a caller would merely move
trust into an unverified structure. Copying a session's full capability set into
every request would also violate least privilege, and a non-atomic replay check
could route the same request concurrently.

Phase 5 will implement authenticated local transport, but Phase 4 needs a runtime-
independent admission boundary that can be proven with in-memory fakes now.

## Decision

Pass Core admission a typed `RequestIdentity` containing principal, session, and
an opaque authority reference. Resolve the authority reference through an
injected trusted registry rather than accepting a caller-provided grant.

Require exact identity binding, active issue/expiry/revocation state, and complete
coverage of every required request capability. Create an immutable effective
permission context containing exactly the requested authorized capabilities.

Reserve the request ID atomically only after permission checks pass. Return an
immutable admitted request or an existing structured failure envelope; never
invoke routing or a runtime from admission.

Tighten `TaskRequest` identity, prompt, capability-count, capability-identity, and
contract-version bounds. Keep the new admission contracts process-internal until
an authenticated transport requires a serialized root.

## Consequences

- Caller-supplied grant fabrication is outside the admission API.
- Missing authority and identity mismatch are indistinguishable to callers.
- Effective authority is least privilege per request.
- A denied request does not consume its ID; an admitted ID is single-use even
  under concurrent attempts.
- Admission failures are bounded, structured, and prompt-free.
- The authority registry becomes a trusted security dependency.
- Restart durability and real credential verification remain future work.

## Alternatives considered

1. Put principal/session directly on `TaskRequest`: rejected because task content
   should not claim its own authenticated identity.
2. Accept a `PermissionGrant` from the caller: rejected because application grants
   do not establish Core transport authenticity and can be fabricated in-process.
3. Copy all session capabilities into the admitted request: rejected as excess
   authority.
4. Reserve request IDs before permission checks: rejected because invalid callers
   could burn valid request IDs.
5. Call the router during admission: rejected because admission must remain
   deterministic and runtime-independent.

## Evidence

- `src/fam_os/core/admission/contracts.py`
- `src/fam_os/core/admission/ports.py`
- `src/fam_os/core/admission/registry.py`
- `src/fam_os/core/admission/service.py`
- `src/fam_os/core/contracts/request.py`
- `tests/unit/test_request_admission.py`
- `tests/architecture/test_core_admission_boundary.py`
