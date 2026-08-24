# Handoff 0151: Production peer state and owner controls

**Date:** 2026-07-17  
**Plan step:** Phase 21.2  
**Status:** Complete  
**Previous handoff:** `0150-production-persistent-peer-identity-and-mtls.md`

## Objective

Turn persistent pairing into an authoritative, inspectable peer trust plane with
signed capabilities, local performance measurements, explicit privacy policy,
trusted-only discovery, and immediate owner-controlled revocation.

## Scope completed

- Added peer-root-signed expert/model/capability declarations and verification.
- Added locally measured TLS round-trip evidence; peer-reported performance is
  not accepted.
- Added migration 0017 and encrypted capability, performance, privacy-policy,
  and replay-safe management-receipt repositories.
- Added active-enrollment-only directory projection that has no enrollment path.
- Added confirmed revision-bound privacy and revocation controls.
- Added close-before-reload live trust replacement plus an active-enrollment
  check on every authenticated control request.
- Added Shell list/probe/privacy/receipts/revoke commands.
- Added authenticated Console APIs and the owner-facing Devices workspace.
- Rendered 228 public schemas.
- Passed the signed seven-component two-install Phase 21.2 exit, including all
  seven installed model declarations, measured latency, privacy, denied missing
  confirmation, immediate and restart-persistent revocation, encrypted labels,
  diagnosis, and complete removal.

## Explicitly not completed

- No prompt, file, memory, retrieved chunk, or remote inference crosses the peer
  boundary. Minimum approved context is Phase 21.3.
- Core/Scheduler remote selection and budgets are Phase 21.4.
- Complete remote evidence, partial-output discard, and disconnect recovery are
  Phases 21.5–21.6.
- Same-host installed evidence is not the physical Phase 21.7 gate.

## Architecture and decisions

ADR 0133 separates peer-signed capability claims from requester-measured
performance. Privacy is deny-all when absent. Directory reads only active
enrollments and cannot create trust. Controls use owner identity, confirmation,
expected revision, exact encrypted payloads, and replay-safe receipts. Revocation
commits before close-and-reload and the handler rechecks active state, preventing
a stale TLS context from retaining control authority.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/fabric/peer_state.py` | Signed capability, performance, privacy, and control contracts |
| `src/fam_os/fabric/peer_directory.py` | Active trusted-only directory projection |
| `src/fam_os/product/storage/peer_state_repository.py` | Encrypted atomic peer state and receipts |
| `src/fam_os/product/storage/migrations/0017_fabric_peer_state.sql` | Peer state tables |
| `src/fam_os/product/peer_management.py` | Probe, discovery, and owner-control service |
| `src/fam_os/product/composition/peer_service.py` | Live trust reload and request-time revocation check |
| `src/fam_os/shell/peer_contracts.py` | Bounded Shell peer surface |
| `src/fam_os/console/peer_routes.py` | Authenticated Console API |
| `src/fam_os/console/static/peers.js` | Devices workspace behavior |
| `tools/phase21_state_exit/` | Installed Phase 21.2 scenario components |

## Public interfaces

- Shell: `/peer list`, `probe`, `privacy`, `receipts`, and `revoke`.
- Console: `GET /api/v1/peers`, `GET /api/v1/peers/receipts`, and
  `POST /api/v1/peers/{enrollment}/probe|privacy|revoke`.
- Peer protocol: authenticated `health` and `describe` operations only.
- Migration: `0017_fabric_peer_state.sql`.

## Validation

```bash
.verification-venv/bin/python tools/run_phase21_peer_state_exit.py
.verification-venv/bin/python -m unittest discover -s tests
.verification-venv/bin/ruff check src tests tools
.verification-venv/bin/mypy <affected Phase 21.2 source files>
PYTHONPATH=src:. .verification-venv/bin/python tools/render_contract_schemas.py --check
git diff --check
```

Result: signed installed exit passed; 1,033 tests passed with two declared
skips; whole-tree Ruff, 33 affected Mypy source targets, 228 schema artifacts,
integration-coverage contracts, and whitespace validation passed.

## Evidence and artifacts

- `artifacts/fabric/phase21.2-peer-state-and-controls.json`
- `docs/decisions/0133-peer-state-is-authenticated-measured-owner-controlled-and-live-revocable.md`
- `tests/integration/test_product_peer_management.py`
- `tests/unit/test_fam_shell_peer_transport.py`
- `tests/integration/test_console_peers.py`

## Known limitations and risks

- Capability declarations refresh on probe and expire after 24 hours.
- Automated TLS leaf renewal remains open.
- Physical firewall, routing, hostname, and loss behavior remain unmeasured.
- No remote context is authorized until Phase 21.3.
- Independent human penetration testing remains open in Phase 23.

## Recommended next entry point

Implement Phase 21.3 with a typed, byte-bounded remote context envelope that
evaluates the stored per-peer policy, defaults to zero disclosure, proves exact
minimization, and still exposes no remote action authority.
