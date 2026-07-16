# ADR 0028: Make tamper-evident Supervisor audit writes required

**Status:** Accepted  
**Date:** 2026-07-16

## Context

Supervisor lifecycle, limit, and access operations change operating-system
state. Optional logging would permit privileged effects without durable caller,
service, operation, and outcome evidence. Free-form logs would also expose user
content and make compatibility or integrity verification ambiguous.

The current user-session deployment cannot honestly provide write-once storage.
It can, however, make each event immutable, require durable append around every
operation, and expose retained-file tampering without expanding the Supervisor
into a general logging or intelligence service.

## Decision

Define a strict v1alpha1 audit intent containing bounded identifiers, enumerated
operation/outcome values, opaque resource IDs, and stable reason/evidence codes.
Use a unique event ID for each record and one operation ID for its requested and
outcome records.

Encode records as canonical JSONL and link them with SHA-256 over the full
unsigned document. Require exact fields, canonical UTC timestamps, monotonic
sequence numbers, the previous digest, unique event IDs, private ownership and
mode, file locking, one append write, and `fsync`.

Compose required auditing above ownership-aware lifecycle, constrained start,
and service access. The requested append precedes effects. If an outcome append
fails after a newly reversible effect, compensate by stopping the new service or
revoking the new grant. Return every audit failure to the caller.

Describe this as tamper-evident append-only storage. Do not claim protection
against full deletion or rollback to an earlier valid prefix without a trusted
external checkpoint.

## Consequences

- Supervisor effects have exact caller, service, operation, resource, and
  outcome linkage.
- Duplicate event identity and retained-file mutation fail closed.
- Audit records cannot carry prompts, content, raw paths, or exception strings.
- Audit availability is now part of Supervisor operation availability.
- Newly started services and applied grants are compensated when their success
  cannot be durably recorded.
- Stop and revoke remain reconciliation cases if their outcome append fails,
  because those safe reductions cannot be meaningfully undone.
- Production assembly must expose audited decorators, not raw adapters.
- Phase 14 still needs external checkpointing, rotation/retention, recovery,
  multi-user ownership, packaging, and backup policy.

## Alternatives considered

1. Best-effort logging: rejected because effects could be silently unaudited.
2. Store exception text and arbitrary details: rejected for privacy and schema
   stability.
3. Use one event for both request and outcome: rejected because a crash between
   effect and outcome would erase evidence that the operation began.
4. Call the local hash chain tamper-proof: rejected because the file owner can
   delete or roll back the ledger.
5. Put audit logic in each Linux adapter: rejected because policy and linkage
   would be duplicated and provider-specific.

## Evidence

- `src/fam_os/supervisor/audit_contracts.py`
- `src/fam_os/supervisor/audit_codec.py`
- `src/fam_os/supervisor/audited_lifecycle.py`
- `src/fam_os/supervisor/audited_constrained.py`
- `src/fam_os/supervisor/audited_access.py`
- `src/fam_os/adapters/audit/jsonl.py`
- `tests/unit/test_supervisor_audit.py`
- `tests/unit/test_jsonl_audit_sink.py`
- `tests/hardware/audited_service_lifecycle_smoke.py`
