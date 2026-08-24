# Handoff 0150: Production persistent peer identity and mutual TLS

**Date:** 2026-07-17  
**Plan step:** Phase 21.1  
**Status:** Complete  
**Previous handoff:** `0149-production-live-adaptation-controls.md`

## Objective

Replace the Phase 12 loopback-only identity and encrypted-channel demonstration
with persistent installed device identity, an explicit manual pairing ceremony,
and a supervised mutually authenticated TLS transport.

## Scope completed

- Added fail-closed owner-private Ed25519 device roots and separately issued
  client/server TLS leaf chains that survive restart without identity replacement.
- Added signed ten-minute pairing offers, symmetric comparison codes, confirmed
  signed approvals, and installed `fam-os peer` configure/offer/code/approve commands.
- Added encrypted revisioned peer enrollment storage in migration 0016.
- Added TLS 1.3-only client/server contexts, certificate-required transport,
  post-handshake device binding, unpaired-certificate rejection, and bounded frames.
- Added a supervised installed listener that remains off without both explicit
  configuration and at least one active enrollment.
- Added typed health-only peer control messages and 219 rendered contract schemas.
- Passed a signed seven-component, two-install pairing, mTLS, restart, diagnosis,
  and complete-removal exit.

## Explicitly not completed

- Capability, performance, and privacy-policy persistence and owner UI are Phase 21.2.
- Remote context and remote task execution are prohibited until Phase 21.3–21.5.
- Disconnect reconciliation and unchanged-acceptance local retry remain Phase 21.6.
- This same-host two-process gate is not the physical two-machine Phase 21.7 gate.

## Architecture and decisions

ADR 0132 supersedes ADR 0099 for production transport. Persistent Ed25519 roots
anchor manual pairing and issue TLS leaves; OpenSSL TLS 1.3 provides the installed
record layer. Pairing codes aid human comparison but do not replace certificate
signatures. Listener configuration is versioned, owner-private, atomic, and
disabled by default. Health is the only accepted protocol operation so the new
network surface cannot bypass future remote-context policy.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/fabric/credentials.py` | Persistent device root and TLS leaf lifecycle |
| `src/fam_os/fabric/pairing.py` | Signed offers, comparison code, and approvals |
| `src/fam_os/fabric/tls_trust.py` | TLS contexts and certificate/device binding |
| `src/fam_os/fabric/tls_transport.py` | Bounded mutual-TLS request transport |
| `src/fam_os/fabric/enrollment.py` | Durable enrollment lifecycle contract |
| `src/fam_os/fabric/peer_control.py` | Health-only wire contracts |
| `src/fam_os/fabric/service_configuration.py` | Versioned listener configuration |
| `src/fam_os/product/composition/peer_service.py` | Installed supervised listener lifecycle |
| `src/fam_os/product/storage/peer_enrollment_repository.py` | Encrypted enrollment repository |
| `src/fam_os/product/storage/migrations/0016_fabric_peer_enrollments.sql` | Peer enrollment table |
| `src/fam_os/product/peer_cli.py` | Owner pairing command operations |
| `tools/phase21_peer_exit/` | Signed two-install qualification components |

## Public interfaces

- Schemas: device pairing offer/approval, endpoint, enrollment, authenticated
  peer, peer control request/response, and peer-service configuration.
- Commands: `fam-os ... peer configure`, `identity`, `offer`, `code`, and `approve`.
- Service flags: `--device-name`, `--peer-listen-host`, and `--peer-listen-port`;
  saved configuration is used when flags do not override it.
- Migration: `0016_fabric_peer_enrollments.sql`.

## Validation

```bash
PYTHONPATH=src:tools .verification-venv/bin/python tools/run_phase21_peer_identity_exit.py
PYTHONPATH=src .verification-venv/bin/python -m unittest discover -s tests
.verification-venv/bin/ruff check src tests tools
PYTHONPATH=src .verification-venv/bin/python -m mypy \
  src/fam_os/fabric src/fam_os/product/composition/core_storage.py \
  src/fam_os/product/composition/peer_control_handler.py \
  src/fam_os/product/composition/peer_service.py \
  src/fam_os/product/peer_cli.py src/fam_os/product/peer_configuration.py \
  src/fam_os/product/service.py src/fam_os/product/service_cli.py \
  src/fam_os/product/storage/peer_enrollment_repository.py
PYTHONPATH=src .verification-venv/bin/python tools/render_contract_schemas.py --check
git diff --check
```

Result: signed exit passed; 1,025 tests passed with two declared skips; Ruff,
affected Mypy targets, 219 schema artifacts, and whitespace validation passed.

## Evidence and artifacts

- `artifacts/fabric/phase21.1-persistent-mtls.json`
- `docs/decisions/0132-production-peer-trust-uses-persistent-device-roots-and-mtls.md`
- `docs/protocols/TRUSTED_MULTIDEVICE_FABRIC.md`

## Known limitations and risks

- TLS leaf renewal is fail-closed but not yet automated before its two-year expiry.
- Enrollment changes require service restart until Phase 21.2 adds controlled live reload.
- Physical network firewall, hostname, routing, and two-machine behavior remain unmeasured.
- Independent human review of the new network surface remains a Phase 23 blocker.

## Operational notes

The peer listener defaults to port 48121 but never binds merely because a device
was discovered. Configuration and active owner enrollment are both required.
Private identity files are mode `0600`; deleting them is destructive identity
reset and is intentionally not an automatic repair action.

## Recommended next entry point

Advance Phase 21.2 in `src/fam_os/fabric/enrollment.py`,
`src/fam_os/product/storage/peer_enrollment_repository.py`, and
`src/fam_os/product/composition/peer_service.py`. Add confirmed live revocation,
capability/performance/privacy records, trusted-only discovery, and Shell/Console
management before any remote context is permitted.
