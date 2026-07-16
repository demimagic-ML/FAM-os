# Handoff 0027: Required tamper-evident Supervisor audit

**Date:** 2026-07-16  
**Plan step:** Phase 3.5 immutable audit-event emission  
**Status:** Complete  
**Previous handoff:** `0026-strong-model-quality-rerun.md`

## Objective

Make Supervisor audit evidence a required, deterministic part of lifecycle,
resource-limit, and access operations. Preserve exact caller/service/operation/
outcome linkage, bounded privacy, durable retained-file integrity evidence, and
safe compensation without claiming local storage is tamper-proof.

## Scope completed

- Added frozen v1alpha1 audit intents and records with strict identity, service,
  resource, reason, evidence, timestamp, digest, and version validation.
- Separated unique event IDs from operation IDs; each request/outcome pair shares
  one operation ID while nested operations use distinct IDs.
- Added canonical exact-key JSON encoding, strict decoding, UTC microsecond
  timestamps, and SHA-256 record digests.
- Added a locked JSONL sink with monotonic sequence links, `O_APPEND`, one write,
  `fsync`, no-follow open, current-owner enforcement, and mode `0600`.
- Added detection for noncanonical records, digest and link changes, truncation,
  oversized records, duplicate event IDs, and insecure targets.
- Made verification return the count and digest of the valid prefix together
  with bounded failure sequence/reason evidence.
- Added required audited compositions for owned lifecycle, constrained service
  start, filesystem/device grant, and grant revocation.
- Prevented effects when the request record cannot be written.
- Added compensating stop/revoke when a newly reversible effect succeeds but its
  outcome cannot be durably written.
- Added stable denial/failure codes without persisting raw exception text.
- Moved immutable audit emission from planned to implemented in the canonical
  Supervisor boundary.
- Added architecture documentation, ADR 0028, and this handoff.
- Ran a real user-systemd audited start/stop proof and refreshed both repository
  discovery indexes.

## Explicitly not completed

- The local hash chain does not prevent full ledger deletion or rollback to an
  earlier valid prefix; a trusted external head checkpoint belongs to Phase 14.
- Rotation, retention, backup, multi-user ownership, and packaging are not part
  of this step.
- Raw OS adapters do not audit themselves; production assembly must expose the
  audited decorators.
- A failed outcome append after stop/revoke is not compensated by recreating the
  service or access. The caller receives an audit error and the request record
  remains for reconciliation.
- Recovery and safe termination are Phase 3.6.
- The external authenticated Supervisor transport remains future work.

## Architecture and decisions

ADR 0028 makes the audit sink part of operation availability. A requested row is
durable before any effect. A second immutable row records succeeded, denied,
failed, or compensated outcome. The operation ID is the correlation key; the
event ID remains unique per row and duplicate event identity fails closed.

Audit fields accept only typed identifiers and enumerated/bounded codes. Prompts,
model output, paths, command lines, raw exceptions, arbitrary metadata, and user
content have no field in the contract.

The retained JSONL file is tamper-evident: canonical decoding and a SHA-256 chain
detect changes, insertion, retained truncation, broken links, and duplicates.
The documentation explicitly excludes full deletion and valid-prefix rollback
from that guarantee.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/supervisor/audit_contracts.py` | Immutable audit event/chain contracts |
| `src/fam_os/supervisor/audit_codec.py` | Canonical encoding and digest verification |
| `src/fam_os/supervisor/audit.py` | Privacy-bounded event construction/emission |
| `src/fam_os/supervisor/audit_outcomes.py` | Stable exception-to-code mapping |
| `src/fam_os/supervisor/audited_lifecycle.py` | Required lifecycle audit and start compensation |
| `src/fam_os/supervisor/audited_constrained.py` | Required limit audit and compensation |
| `src/fam_os/supervisor/audited_access.py` | Required grant/revoke audit and compensation |
| `src/fam_os/supervisor/ports/audit.py` | Provider-neutral audit sink port |
| `src/fam_os/adapters/audit/jsonl.py` | Durable private JSONL hash-chain sink |
| `src/fam_os/supervisor/boundary.py` | Audit capability marked implemented |
| `tests/unit/test_supervisor_audit.py` | Contract, codec, and privacy tests |
| `tests/unit/test_jsonl_audit_sink.py` | Durability, integrity, duplicate, and concurrency tests |
| `tests/unit/test_audited_lifecycle.py` | Required lifecycle and linkage tests |
| `tests/unit/test_audited_constrained.py` | Nested linkage and limit compensation tests |
| `tests/unit/test_audited_access.py` | Grant/revoke linkage and compensation tests |
| `tests/hardware/audited_service_lifecycle_smoke.py` | Real user-service audit proof |
| `docs/architecture/IMMUTABLE_SUPERVISOR_AUDIT.md` | Invariants and honest integrity boundary |
| `docs/decisions/0028-required-tamper-evident-supervisor-audit.md` | Required-audit decision |

## Public interfaces

- `SupervisorAuditIntent`, `SupervisorAuditRecord`, `AuditChainVerification`
- `SupervisorAuditOperation`, `SupervisorAuditOutcome`
- `SupervisorAuditEmitter.new_operation_id()` and `.emit(...)`
- `SupervisorAuditSink.append(...)` and `.verify()`
- `JsonlHashChainAuditSink`
- `AuditedOwnedServiceLifecycle`
- `AuditedConstrainedServiceLifecycle`
- `AuditedServiceAccessController`

## Validation

```bash
PYTHONPATH=src python3 -m unittest \
  tests.unit.test_supervisor_audit \
  tests.unit.test_jsonl_audit_sink \
  tests.unit.test_audited_lifecycle \
  tests.unit.test_audited_access \
  tests.unit.test_audited_constrained
```

Result: all 25 focused audit tests passed in 0.040 seconds.

```bash
FAM_AUDIT_LIFECYCLE_SMOKE=1 PYTHONPATH=src:. \
  python3 -m unittest tests.hardware.audited_service_lifecycle_smoke -v
```

Result: the real user-systemd start/stop smoke passed in 0.041 seconds. Four
requested/succeeded records formed one valid chain and the private transient
ledger was mode `0600`; cleanup left the service inactive.

```bash
PYTHONPATH=src:. python3 -m unittest discover -s tests
PYTHONPATH=src:. python3 tools/render_contract_schemas.py --check
python3 -m compileall -q src tools tests
```

Result: all 313 tests passed in 0.243 seconds, all 35 generated schemas matched,
and compilation completed successfully. The prior completed suite had 311 tests.

An AST audit found no `src/` or `tools/` module at or above 300 lines and no
function at or above 50 lines.

Larry refreshed 459 files and verified clean. The codebase
graph refreshed in fast mode with 6,892 nodes and 20,548 edges.

## Known limitations and risks

- A valid-prefix rollback needs an external trusted head to detect.
- SHA-256 linkage provides integrity evidence, not secrecy or write-once storage.
- `fsync` failure can occur after a write reaches the page cache; the caller sees
  failure and later verification/reconciliation determines durable state.
- Concurrent writers are safe only when they honor the same advisory file lock.
- The current sink has no rotation policy; unsafe external mutation fails closed.
- Audited wrappers must be the only production entrypoint to the raw adapters.
- Stop/revoke outcome-write failure is a reconciliation case, not a reason to
  undo a safe reduction in authority.

## Recommended next entry point

Begin Phase 3.6 from `SupervisorAuditOperation.RECOVER_SERVICE` and
`TERMINATE_SERVICE`. Define provider-neutral recovery/termination contracts,
coordinate stop with grant revocation, require terminal status and resource
evidence, audit every state transition through the existing sink, and add a real
transient-service failure/cleanup smoke before marking the step complete.
