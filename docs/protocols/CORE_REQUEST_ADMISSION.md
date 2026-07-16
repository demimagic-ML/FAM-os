# Core request admission and permission context

## Invariant

No request reaches routing until FAM Core has bound it to one active trusted
authority record, an exact principal/session, an unexpired capability scope, and
a single-use request ID.

```text
typed TaskRequest + transport identity
  -> trusted authority registry lookup
  -> principal/session/authority binding
  -> issue/revocation/expiry check
  -> required-capability subset check
  -> atomic replay reservation
  -> immutable admitted request + least-privilege permission context
```

This step has no inference, application, Supervisor, scheduler, verifier, desktop,
Ollama, systemd, or hardware dependency.

## Contracts

`RequestIdentity` carries the principal, session, and opaque authority reference
already established by a future authenticated local transport.

`RequestAuthorityGrant` is trusted registry state. It binds that authority
reference to exactly one principal/session, a canonical sorted set of granted
capabilities, issue time, mandatory expiry, and optional revocation time.

`RequestPermissionContext` is the effective authority attached to an admitted
request. It deliberately contains only the request's required capabilities in
request order. It does not copy every capability held by the session authority.

`AdmittedTaskRequest` binds the immutable task, permission context, admission ID,
and admission time. Construction fails unless admission precedes expiry and the
effective capabilities exactly equal the request requirements.

`RequestAdmissionOutcome` contains exactly one admitted request or one structured
`FailureEnvelope`. Rejections contain no prompt or provider exception.

## Admission behavior

The authority registry is injected and trusted; the caller cannot supply an
arbitrary grant object directly to `RequestAdmissionService`. Missing authority
and principal/session mismatch intentionally return the same code and safe
message to avoid identity enumeration.

Future-issued, expired, and revoked authorities return
`admission.authority_inactive`. Missing capability scope returns
`admission.capability_denied` linked to the first missing capability. These are
permission failures that require user action.

The replay registry reserves a request ID only after all authority checks pass.
Thus a denial cannot burn another valid request, while an admitted ID can never
be routed twice. The in-memory implementation uses a lock so concurrent attempts
produce exactly one reservation.

## Input bounds

`TaskRequest` now requires a bounded identifier, exact current contract version,
a nonempty NUL-free prompt of at most 131,072 characters, no more than 64 unique
bounded capability IDs, and strict capability identifiers. Multiline prompt
content remains valid; control restrictions apply to identities, not user prose.

These stricter domain checks supplement the existing exact v1alpha1 serialized
shape. Admission contracts are internal Python contracts in Phase 4.1; a new
serialized root is deferred until an authenticated transport needs to cross the
process boundary.

## Failure and privacy boundary

Admission uses existing `fam.failure/v1alpha1` envelopes:

- `admission.authority_denied` for missing or mismatched identity binding;
- `admission.authority_inactive` for time/revocation failure;
- `admission.capability_denied` for insufficient scope;
- `admission.request_replayed` for an already admitted request ID.

Safe messages are fixed. They do not include prompt text, registry contents,
credentials, exception strings, or the identity that failed.

## Current limitations

- The in-memory authority and replay registries are not restart-durable.
- Grant authenticity is established by trusted registry insertion; the external
  authentication/credential adapter is Phase 5.2 work.
- Cancellation, deadlines, approval state, and permission expiry during a running
  plan belong to later Phase 4 steps.
- Admission does not route, plan, execute, or release a result.

## Evidence

Unit tests cover least privilege, missing/mismatched indistinguishability,
future/expired/revoked authority, capability denial, denial without ID burn,
successful replay rejection, concurrent atomic reservation, malformed contracts,
and ambiguous outcome rejection. An architecture test forbids runtime and
external-boundary imports from the admission package.
