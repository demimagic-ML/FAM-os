# Required Supervisor audit chain

## Invariant

Every audited Supervisor operation writes a canonical `requested` record before
the operating-system or access adapter is invoked. It then writes one bounded
outcome record using the same operation ID. A failed required write is returned
to the caller; it is never silently ignored.

```text
authenticated call context
  -> immutable audit intent
  -> durable requested record
  -> authorized Supervisor operation
  -> durable succeeded, denied, failed, or compensated record
```

The event ID identifies one ledger row. The operation ID links the request and
outcome rows. Request, authority, principal, session, service, operation,
resource, reason, and evidence fields remain independently typed so an event
cannot substitute free-form text for identity or policy evidence.

## Canonical ledger

`JsonlHashChainAuditSink` stores one canonical JSON record per line. Every record
contains a monotonically increasing sequence, the previous digest, and a SHA-256
digest over its complete unsigned document. Decoding rejects unknown or missing
fields, noncanonical JSON, malformed timestamps, invalid identities, broken
sequence links, digest changes, duplicate event IDs, oversized lines, and a
truncated final record.

Append and verification take a file lock. Append uses one `O_APPEND` write and
`fsync`; the file must be a regular file owned by the current user with mode
`0600`, and symbolic links are rejected. An invalid existing chain blocks every
later append. Verification reports the count and digest of the last valid prefix
as well as the failing sequence and bounded reason code.

## Required composition

The audited lifecycle, constrained-lifecycle, and service-access decorators make
the ledger part of the operation rather than optional telemetry:

- a failed request append prevents the operation;
- a failed start-outcome append stops a service that was newly started;
- a failed grant-outcome append revokes the newly applied grant;
- a resource-limit mismatch stops the service and records `compensated`;
- authorization and adapter failures record stable reason codes, never raw
  exception messages.

A service that was already active is not stopped to compensate for a repeated
start. Stop and revoke cannot be undone when their outcome append fails; the
caller receives the audit error and the durable requested record remains for
reconciliation.

Raw adapters do not audit themselves. Production composition must expose the
audited decorators rather than allowing Core to call a raw lifecycle or access
adapter directly.

## Privacy boundary

The v1alpha1 event contains identifiers and enumerated codes only. It does not
accept prompts, model output, file paths, command lines, exception strings, user
content, or arbitrary metadata. Resource IDs are opaque namespaced identifiers;
Linux paths remain inside trusted adapters.

## Integrity boundary

This design is append-only and tamper-evident, not tamper-proof. The hash chain
detects modification, insertion, truncation within a retained file, and repeated
event IDs. A filesystem owner can still delete the complete ledger or roll it
back to an earlier valid prefix. Detecting that requires a trusted external head
checkpoint, remote journal, or write-once storage. That production durability
belongs to Phase 14 and must not be implied by Phase 3.5 evidence.

## Evidence

Unit tests cover canonical encoding, immutability, strict decoding, duplicate
event IDs, concurrent append, permissions, truncation, tampering, valid-prefix
reporting, required-before-operation behavior, exact operation linkage, stable
failure codes, and compensation.

The opt-in hardware smoke starts and stops a real transient user service through
the audited lifecycle. It verifies four durable linked records, the complete
hash chain, private file mode, and service cleanup.
