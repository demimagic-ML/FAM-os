# Handoff 0153: Production remote Core route

**Date:** 2026-07-17  
**Plan step:** Phase 21.4  
**Status:** Complete  
**Previous handoff:** `0152-production-minimum-remote-context.md`

## Objective

Make an explicitly authorized trusted-peer expert a normal Scheduler-selected
Core route without creating a second lifecycle or weakening budget,
verification, terminal, privacy, or learning policy.

## Scope completed

- Added exact remote authority, route plan, signed request, and signed result
  contracts with bounded context, output, time, identity, digest, and metric
  invariants.
- Added peer-root request/result signing and verification plus mutual-TLS
  certificate echo binding.
- Refactored Phase 21.3 disclosure into reusable prepare/record operations so
  policy is rechecked immediately before inference and evidence stays
  content-free.
- Added trusted-directory, authenticated-performance, signed-capability, and
  Fabric-Scheduler route planning during normal Core admission.
- Added one remote attempt to the existing durable global budget and fed its
  complete candidate through the existing verifier and final-result policy.
- Preserved bounded local repair after a rejected remote candidate.
- Bound peer capability and remote plan to the real expert tier; remote placement
  no longer masquerades as an expert tier in verified-outcome learning.
- Added peer receiver execution through the installed runtime and product
  composition for client, planner, server, listener, Core, Shell, and Console.
- Added the explicit `/remote ask ... --confirm` Shell surface and Console
  Devices task dialog. Ordinary requests remain local unless this authority is
  present.
- Denied remote media until a binary-context authority exists.
- Added four public schemas, bringing the generated catalog to 238 roots.
- Added focused signature, tamper, policy-revision, remote-success,
  verifier-driven local-repair, learning, Shell, Console, and mTLS tests.

## Installed exit evidence

A fresh Ed25519-signed seven-component release was installed into two isolated
prefixes and paired through the real comparison ceremony. The installed desktop
probed the peer, stored an exact privacy scope, and submitted an authenticated
Console task. Core selected downloaded `gemma4:26b`, persisted an escalation-tier
remote plan, reserved one `remote` attempt, disclosed one exact prompt fragment,
received a peer-signed complete result, and released `READY` only after the
signed exact-text verifier passed.

The gate also proved missing confirmation, stale privacy revision, unapproved
workspace, and excessive context are denied without persisting a request or
changing receiver evidence. An ordinary verified task had no remote plan, no
remote reservation, and no additional peer disclosure. Installed-code
inspection proved the remote/local route distinction. Neither content-free
evidence nor either SQLite database contained the prompt. Both installations
diagnosed healthy and were completely removed.

## Explicitly not completed

- Phase 21.5 must persist one complete remote-execution evidence record and prove
  that partial or unauthenticated output is never retained or released.
- Phase 21.6 must reconcile disconnects, uncertain completion, durable budget,
  and local retry under unchanged acceptance.
- Phase 21.7 must repeat the final scenario between two physical Linux machines;
  this gate used two isolated installations on one workstation.
- Remote binary media remains denied pending its own exact context contract.

## Principal files

| Path | Purpose |
|---|---|
| `src/fam_os/fabric/remote_execution.py` | Authority, plan, request, and result contracts |
| `src/fam_os/fabric/remote_execution_signing.py` | Peer-root signing and verification |
| `src/fam_os/product/remote_execution_planner.py` | Trusted eligible route planning |
| `src/fam_os/product/remote_execution_client.py` | Sender-side mTLS execution port |
| `src/fam_os/product/remote_execution_server.py` | Receiver-side installed expert runtime |
| `src/fam_os/core/production/execution_worker.py` | Shared budget and candidate path |
| `src/fam_os/core/production/verification_flow.py` | Same verifier and local repair path |
| `src/fam_os/product/service.py` | Installed product composition |
| `src/fam_os/shell/remote_terminal.py` | Explicit Shell authority |
| `src/fam_os/console/static/peers.js` | Console Devices task surface |
| `tools/phase21_remote_exit/` | Signed installed qualification |

## Validation

```bash
PYTHONPATH=src:. .verification-venv/bin/python tools/run_phase21_remote_exit.py
PYTHONPATH=src:. .verification-venv/bin/python -m unittest discover -s tests
PYTHONPATH=src:. .verification-venv/bin/python tools/render_contract_schemas.py --check
.verification-venv/bin/ruff check src tests tools
.verification-venv/bin/mypy <affected Phase 21.4 source and tools>
git diff --check
```

Result: the signed installed gate passed with real Gemma inference, exact signed
verification, four pre-disclosure denial classes, one remote reservation, one
disclosure per installation, an ordinary local route, no plaintext prompt in
evidence or SQLite, healthy diagnosis, and complete removal. The full source
suite passes 1,045 tests with two declared skips; all 238 schemas validate.

## Evidence

- `artifacts/fabric/phase21.4-remote-core-route.json`
- `tests/unit/test_remote_execution.py`
- `tests/integration/test_product_remote_execution.py`
- `tests/integration/test_mutual_tls_peer_transport.py`
- `tests/unit/test_fam_shell.py`
- `tests/integration/test_console_http.py`
- `tests/integration/test_console_peers.py`

## Next step

Phase 21.5 must bind one durable complete remote-execution evidence record to the
Core request, plan, disclosure receipt, signed result, candidate, verifier, and
budget identities. Truncated, timed-out, unsigned, or otherwise partial output
must leave no releasable candidate or durable content.
