# Handoff 0152: Production minimum remote context

**Date:** 2026-07-17  
**Plan step:** Phase 21.3  
**Status:** Complete  
**Previous handoff:** `0151-production-peer-state-and-owner-controls.md`

## Objective

Permit an owner-approved trusted peer to receive only the minimum exact context
needed for a future remote task, while proving that every unauthorized prompt,
file excerpt, memory value, and retrieval value is denied before the network.

## Scope completed

- Added strict task descriptor, raw fragment, signed envelope, signed receipt,
  local send request, and content-free evidence contracts.
- Removed the provisional zero-digest construction path; every public envelope
  now has valid exact-byte evidence and a 64-byte Ed25519 signature at creation.
- Added fail-closed outbound evaluation of active enrollment, exact policy
  revision, owner/peer/purpose/workspace/sensitivity/bytes/raw scope, selected
  signed capability declaration, expert, required capabilities, and byte ceiling.
- Added receiver-side sender signature, target, validity, exact-byte, and current
  installed-capability checks before a receipt is signed.
- Added migration 0018 and encrypted content-free inbound/outbound evidence with
  replay identity binding.
- Added authenticated Console context/evidence endpoints and Shell descriptor
  transfer/evidence commands.
- Added six public schema roots, bringing the generated catalog to 234 schemas.
- Added exact-byte, signature, receipt, policy, capability, raw-kind, at-rest,
  Shell, Console, and real mutual-TLS integration tests.
- Passed a fresh signed seven-component two-install exit using the installed
  Gemma 4 26B expert declaration, then diagnosed and completely removed both.

## Explicitly not completed

- A context receipt is not remote inference. Core/Scheduler/budget/verifier
  execution integration is Phase 21.4.
- Complete remote result evidence and partial-output discard are Phase 21.5.
- Lost-response/disconnect reconciliation and unchanged-acceptance retry are
  Phase 21.6.
- The gate uses two isolated signed installations on one host, not the two
  physical Linux machines required by Phase 21.7.

## Architecture and decisions

ADR 0134 makes privacy evaluation local and pre-network, makes the disclosed
payload exact rather than descriptive, and separates a peer-signed disclosure
receipt from future execution evidence. Raw content is never persisted or
returned through management surfaces. The peer transport remains mutual TLS 1.3
and the installed capability is rechecked on the receiver independently of the
sender's selected declaration.

## Principal files

| Path | Purpose |
|---|---|
| `src/fam_os/fabric/context.py` | Exact-byte context and receipt contracts |
| `src/fam_os/fabric/context_signing.py` | Ed25519 creation and verification |
| `src/fam_os/fabric/context_evidence.py` | Local request and content-free evidence |
| `src/fam_os/product/peer_context.py` | Fail-closed outbound service |
| `src/fam_os/product/composition/peer_control_handler.py` | Authenticated receiver validation |
| `src/fam_os/product/storage/peer_context_repository.py` | Encrypted evidence repository |
| `src/fam_os/product/storage/migrations/0018_fabric_remote_context.sql` | Evidence table |
| `src/fam_os/console/peer_context_routes.py` | Strict Console endpoint |
| `src/fam_os/shell/peer_contracts.py` | Shell transfer/evidence response |
| `tools/phase21_context_exit/` | Signed installed scenario |

## Public interfaces

- Peer control operation: `context` with a signed minimum-context envelope.
- Shell: `/peer context ...` and `/peer context-evidence`.
- Console: `POST /api/v1/peers/{enrollment}/context` and
  `GET /api/v1/peers/context-evidence`.
- Migration: `0018_fabric_remote_context.sql`.
- Schemas: six `fam.fabric.*context*` roots under `schemas/v1alpha1/`.

## Validation

```bash
.verification-venv/bin/python tools/run_phase21_context_exit.py
.verification-venv/bin/python -m unittest discover -s tests -t .
.verification-venv/bin/ruff check .
.verification-venv/bin/mypy <53 affected source files>
.verification-venv/bin/python tools/render_contract_schemas.py
git diff --check
```

Result: signed installed exit passed with all eight denial categories, unchanged
receiver count across denials, three verified disclosures per installation, no
raw sentinel in evidence or SQLite, healthy diagnosis, and complete removal.
The full suite passed 1,036 tests with two declared skips; Ruff, affected Mypy,
234 schema artifacts, and contract round trips passed.

## Evidence

- `artifacts/fabric/phase21.3-minimum-context.json`
- `tests/unit/test_remote_context.py`
- `tests/integration/test_product_peer_context.py`
- `tests/unit/test_fam_shell_peer_transport.py`
- `tests/integration/test_console_peers.py`

## Next step

Phase 21.4 must route real remote execution through the existing durable Core,
Scheduler, global attempt budget, production verifier bindings, and unchanged
acceptance contract. Do not build a parallel remote-task lifecycle.
