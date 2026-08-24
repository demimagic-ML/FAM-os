# Durable product storage

The Phase 17 production database lives beneath the owner-private state root. It
opens only after owner, mode, file type, link count, WAL availability, foreign
keys, migration history, and integrity have been checked.

Migration filenames are contiguous (`0001_name.sql`, `0002_name.sql`, ...).
Each applied migration records its SHA-256 digest. Editing an applied migration
or opening a database created by unknown future migrations is a hard failure.
Schema and migration-record creation occur in the same immediate transaction.

The initial schema separates requests, plans, ordered events, scoped authorities,
decisions, idempotent actions, digest-bound evidence references, expert state,
connector state, and verified-evidence-linked adaptation metadata. Prompt,
context, scope, action payload, postcondition, expert details, connector details,
and adaptation features have dedicated ciphertext columns; plaintext is not a
supported persistent representation.

Phase 20.5 adds owner-encrypted terminal results and verified-learning outcomes.
Once the presented terminal result is retained, the same transaction replaces
durable request/application prompt copies, candidate text, and verifier feedback
with one fixed marker and removes the completed verifier declaration. Learning
records contain only closed workflow/model buckets and evidence bindings; raw
prompt, candidate, source, and application content are not valid fields.

Phase 20.6 adds owner-encrypted immutable live-adaptation snapshots and prewarm
receipts. Snapshots contain only intent-scoped aggregate context, frequency,
escalation, transition, and source-identity metadata. Receipts bind the snapshot,
candidate model, live resource reservation, residency outcome, timing, and reason
codes. They contain no request prompt or model output.

Phase 20.7 adds migration 0015 with one revisioned owner control state plus
encrypted control receipts, pending inference observations, repeated health
samples, and drift reports. Snapshot foreign keys cascade derived inference,
health, drift, and prewarm data during reset. Reset also removes verified
learning in the same transaction, but terminal results and the control receipt
ledger are deliberately retained. Plaintext columns contain only owner,
identity, workflow, operation, revision, and relationship indexes; health,
control state, report metrics, reason codes, and receipt removal counts remain
inside owner-bound ciphertext.

Callers use bounded domain repositories and never share raw SQL outside the
storage composition unit. Phase 17.2 introduces fail-closed owner key handling;
Phase 17.3 introduces the durable Core repositories.
