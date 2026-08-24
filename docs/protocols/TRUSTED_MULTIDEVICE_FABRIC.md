# Trusted multi-device fabric

Production Phase 21 uses persistent device roots and TLS 1.3 mutual
authentication. The Phase 12 signed-X25519/AES-GCM channel remains historical
loopback evidence and is not the installed socket transport.

## Configure each device

The listener is off by default. Configure the private bind address and the
address the other device can actually reach:

```bash
fam-os --prefix PREFIX --trusted-key KEY_ID=PUBLIC_KEY.pem \
  peer --state-root STATE --device-name "Home server" configure \
  --listen-host 0.0.0.0 --listen-port 48121 \
  --advertised-host server.lan --advertised-port 48121 --confirm
```

The generated user service reads `STATE/config/peer.json` on every start. It
does not listen until an active peer enrollment also exists.

## Pair two devices

On both machines, emit a signed offer and exchange the files through an
owner-chosen channel:

```bash
fam-os ... peer --state-root STATE --device-name "Desktop" offer > desktop.json
fam-os ... peer --state-root STATE --device-name "Home server" offer > server.json
```

Each machine verifies both signatures and displays the same comparison code:

```bash
fam-os ... peer --state-root STATE --device-name "Desktop" code \
  --local-offer desktop.json --peer-offer server.json
```

After comparing the code through a separate human-visible channel, approve on
each device:

```bash
fam-os ... peer --state-root STATE --device-name "Desktop" approve \
  --local-offer desktop.json --peer-offer server.json \
  --code 0000-0000-0000 --confirm
```

The example code is a placeholder; use the exact code both devices display.
Offers expire after ten minutes. Approval stores no comparison code. Missing
confirmation stores nothing.

## Inspect and control trusted peers

FAM Shell exposes the same owner service as Console's **Devices** workspace:

```text
/peer list
/peer probe ENROLLMENT_ID
/peer privacy ENROLLMENT_ID PRIVACY_REVISION BYTES SENSITIVITIES PURPOSES WORKSPACES RAW_BOOL REASON --confirm
/peer receipts
/peer context ENROLLMENT EXPERT DECLARATION POLICY_REV PURPOSE WORKSPACE SENSITIVITY INTENT CAPABILITIES ASSURANCE MAX_OUTPUT
/peer context-evidence
/peer revoke ENROLLMENT_ID ENROLLMENT_REVISION REASON --confirm
```

`probe` requests a device-root-signed declaration of exact installed models,
capabilities, manifest digests, and context ceilings. Latency is measured by the
requesting device over the authenticated connection; it is not accepted as a
peer claim. Repeated measurements are retained with a bound of 100 per peer.

Privacy is deny-all until the owner stores an explicit scope for exactly one
peer. The policy limits purpose, workspace, sensitivity, byte count, and raw
content. Privacy revisions are separate from enrollment revisions. Revocation
uses the enrollment revision, closes the listener before rebuilding trust, and
survives restart.

Console provides equivalent authenticated endpoints beneath `/api/v1/peers`.
All mutations require the local session, Origin, CSRF token, exact request
fields, expected revision, and explicit confirmation.

## Transfer minimum approved context

The standalone `context` operation is pre-execution disclosure, not action
authority. The sender signs a two-minute envelope containing a canonical
task descriptor and, only when explicitly requested, typed raw fragments. The
exact canonical bytes and SHA-256 digest cover expert, purpose, workspace,
sensitivity, intent, required capabilities, assurance, output ceiling, and all
raw fragment metadata and content.

The sender refuses network access unless all of these are true:

- the enrollment is active;
- the exact expected encrypted privacy-policy revision is current;
- owner, peer, purpose, workspace, sensitivity, byte ceiling, and raw-content
  rules all allow the disclosure;
- the selected unexpired peer-root-signed capability declaration names the same
  peer and expert, contains every required capability, and permits the bytes;
- every raw prompt, file excerpt, memory value, or retrieval value was supplied
  as an explicit digest-bound fragment with confirmation.

The receiver re-authenticates the sender identity, verifies the envelope
signature and exact bytes, rechecks that its current installed expert supports
the descriptor, and returns a device-root-signed content-free receipt. Both
machines encrypt only content-free evidence: request/context/receipt identities,
digests, byte counts, fragment digests, policy revision, capability declaration,
and reason codes. Raw content is discarded after handling and is absent from
Shell, Console evidence, and SQLite payloads.

Console exposes `POST /api/v1/peers/{enrollment}/context` and
`GET /api/v1/peers/context-evidence`. The POST body is exact-field validated;
raw fragments require literal `confirmed: true`. The Shell command intentionally
supports descriptor-only transfer.

## Execute an explicitly remote Core task

Remote execution is opt-in per task. Pairing, discovery, or model availability
never changes ordinary routing. FAM Shell requires the exact peer enrollment,
privacy revision, purpose, workspace, sensitivity, context/output ceilings, and
literal confirmation:

```text
/remote ask ENROLLMENT POLICY_REV PURPOSE WORKSPACE SENSITIVITY CONTEXT_BYTES OUTPUT_BYTES [--verify] --confirm PROMPT
```

Console exposes the equivalent task form in the **Devices** workspace. Both
surfaces submit the same `RemoteExecutionAuthority` to normal Core admission.
The trusted directory supplies current signed capabilities and locally measured
latency; the Fabric Scheduler selects the eligible peer expert. The selected
expert retains its real economical, specialist, escalation, or embedding tier.
Remote placement is represented separately by the persisted remote plan and
`remote` attempt reservation.

The worker uses the same prepared generation input as local execution, creates
one exact Phase 21.3 disclosure, and sends a device-root-signed execution request
over mutual TLS. The receiver rechecks its current enabled expert, runs it in
memory, and returns a peer-signed bounded result. The sender verifies request,
plan, model, result digest, metrics, context receipt, both device roots, and the
requester TLS certificate before creating candidate evidence. That candidate
then enters the same declared verifier, final-result policy, learning, and
bounded local-repair path as a local candidate.

Remote media is denied because the UTF-8 context contract does not authorize
binary image or audio bytes. A separate exact binary-context contract is
required before that route can be enabled.

## Bind complete remote evidence

After the sender has authenticated the complete peer-signed result, Core
atomically stores the candidate with one encrypted, content-free
`RemoteExecutionEvidence`. It binds request and plan identities and digests,
execution request/result digests, enrollment, peer, expert, model and tier,
capability declaration, exact context digest and byte count, peer receipt,
global budget reservation and attempt, candidate and result digests, and the
authentication time. No raw content or partial output is a legal field.

The record begins as `authenticated_candidate`. Verification finalizes it once
as `released`, `rejected`, or `withheld`, with the exact acceptance evidence and
signed verifier run when applicable. Verified acceptance and remote-evidence
finalization commit atomically. Final-result policy rechecks the evidence against
the request, candidate, disposition, and terminal plan reference before release.
Rejected remote evidence remains audit-visible while a permitted local repair
uses a new candidate.

Console exposes the content-free audit record at
`GET /api/v1/tasks/{task}/remote-execution`. A local task or incomplete remote
exchange returns `available: false`. Truncated, timed-out, unsigned, or
identity-mismatched responses create no candidate and no remote-execution
evidence.

## Reconcile loss without changing acceptance

Before networking, Core hashes the exact durable request, active authority,
immutable execution plan, remote route, and verifier declaration. The remote
budget reservation binds that digest and route plan, and the inference record is
marked consumed before the socket opens. A restarted worker therefore never
re-sends an uncertain remote attempt or treats it as free.

Disconnect, timeout, partial response, uncertain completion, and authenticated
remote-provider failure may enter recovery. Policy/authority change,
authentication failure, invalid contract, or digest mismatch deny retry. Core
recomputes the acceptance digest, requires equality and still-active authority,
selects an admissible local model, and reserves one distinct `local_recovery`
attempt under the same global token/time budget. Partial remote bytes are never
used as local context or feedback.

The local candidate passes through the unchanged verifier and final-result
policy. Content-free `RemoteRecoveryEvidence` binds the failure class, both
acceptance digests, remote and local reservations, local selection and candidate,
and final disposition. Crashes after either atomic candidate transaction resume
from retained evidence rather than re-running the model. Console exposes the
record at `GET /api/v1/tasks/{task}/remote-recovery`.

## Current production boundary

The listener accepts `fam.fabric.peer-control/v1alpha1` health, describe, and
pre-execution context requests plus the separate signed
`fam.fabric.remote-execution/v1alpha1` request. Describe returns signed
capability metadata; context accepts only the signed
`fam.fabric.minimum-context/v1alpha1` envelope; remote execution validates that
same envelope before running the exact current installed expert.
TLS requires an enrolled root on both sides and post-validates the device SAN,
issuer, leaf signature, validity, and expected device identity. A one-MiB frame
limit applies before decoding.

Remote inference, Core/Scheduler selection, shared budgeting, normal
verification, durable complete-execution evidence, partial-output discard,
restart reconciliation, and unchanged-acceptance local retry are
production-wired. Two-physical-machine qualification remains Phase 21.7.
Privacy remains deny-by-default across owner, device, purpose, workspace,
sensitivity, byte count, and raw-content use. Localhost qualification is not
physical multi-machine evidence.

Phase 21.7 qualification additionally requires strict content-free
`PhysicalHostEvidence` from two independently discovered non-virtual Linux
hosts. The report validator rejects equal machine or hardware-anchor hashes,
different signed releases, loopback-only networking, unhealthy installations,
missing success/loss evidence, or incomplete removal. A same-host harness may
test protocol behavior but can never satisfy this physical boundary.
