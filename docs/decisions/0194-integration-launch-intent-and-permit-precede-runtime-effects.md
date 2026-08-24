# ADR 0194: Integration launch intent and permit precede runtime effects

Status: Accepted

Resolves: the pre-result orphan-discovery limitation recorded by ADR 0193.

## Context

Product previously persisted an integration environment only after every
backend returned a normal start result. A process exit or simultaneous launch
and compensation failure before that commit could leave deterministic runtime
effects and candidate journals without a product repository record, so startup
could not discover or reconcile them. Pending secret-bearing effects were also
outside the active set drained by rotation or deletion.

## Decision

Migration 0032 adds an owner-scoped integration start-intent table. The exact
plan and candidate are AES-GCM encrypted before authorization begins. Core
continues to own authorization and permit minting, but invokes a replaceable
observer after the complete permit is constructed and before calling any
executor. Product binds that callback to encrypted permit persistence. If
permit persistence fails, no runtime effect is attempted.

A normal start atomically inserts the existing active/failed environment record
and marks its intent committed. A denial or interruption before permit
persistence closes as `prelaunch_failed`, because the executor was unreachable.
An exception after permit persistence becomes `recovery_required`. If normal
result persistence fails and direct compensation succeeds, its cleanup receipt
is stored as the terminal intent recovery instead.

At composition startup, product processes incomplete intents before serving
owner surfaces. Pre-permit intents close without an adapter call. Permitted
intents invoke the selected adapter's recovery operation over the encrypted
plan, candidate root, and exact permit. Docker probes only deterministic
environment-labeled container and network names. Process recovery probes only
deterministic systemd unit and secret-root names. Mixed recovery probes all
backend branches in reverse order, including a branch whose effect occurred
before its composite launch marker was persisted. Successful evidence is
encrypted and the intent becomes `recovered`; failures remain pending.

Recovery evidence deliberately says `recovery-probed-*`: absence of an exact
runtime is a successful negative probe, not a false claim that a runtime was
observed and removed. Candidate retained artifacts are captured only after all
recovery branches are terminal.

Secret rotation and deletion inspect both active environments and pending
intents while holding the shared lifecycle lock. A matching permitted intent
must recover successfully before secret mutation. If its backend is
unavailable or recovery fails, mutation is denied. A matching effect-free
prelaunch intent closes safely.

## Consequences

- Every product start request has durable encrypted intent before effects and
  durable exact permit before executor entry.
- Startup can clean pre-result Docker, process, and groupable mixed effects
  without scanning arbitrary host resources.
- The real installed mixed scenario deliberately omits normal result commit,
  reopens storage, recovers both runtime families, and stores a terminal receipt.
- Start-intent rows are durable audit artifacts, including committed,
  prelaunch-failed, recovery-required, and recovered outcomes.
- Console and Shell do not yet expose start-intent metadata or recovery
  receipts; owner-visible recovery audit remains a product-surface gap.
- If the required concrete adapter is unavailable, recovery remains pending and
  matching secret mutation fails closed.

## Alternatives considered

- Scan all Docker/systemd resources at startup: rejected because broad discovery
  is less authoritative than encrypted intent plus deterministic identities.
- Persist only a plan after a failed launch: rejected because recovery must bind
  the exact admitted permit.
- Mark every exception failed without recovery: rejected because an exception
  does not prove absence of runtime effects.

## Evidence

- `src/fam_os/product/storage/migrations/0032_integration_start_intents.sql`
- `src/fam_os/product/storage/integration_start_intent_repository.py`
- `src/fam_os/product/storage/integration_environment_repository.py`
- `src/fam_os/core/engineering/integration_environment_service.py`
- `src/fam_os/product/integration_environment_api.py`
- `src/fam_os/adapters/integration/docker_environment.py`
- `src/fam_os/adapters/integration/process_recovery.py`
- `src/fam_os/adapters/integration/composite_environment.py`
- `tests/integration/test_real_mixed_integration_environment.py`
- `artifacts/engineering/phase27/integration-environment-installed-20260719-attempt13.json`
