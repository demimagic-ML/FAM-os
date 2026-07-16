# Failed-service recovery and safe termination

## Invariant

Recovery is a deterministic return to a verified inactive baseline. It is not an
automatic restart decision. A successful report proves that the exact owned FAM
service is inactive, has no main PID, and has no unrevoked access grants in the
Supervisor registry.

```text
authenticated owner + dedicated capability
  -> durable recovery/termination request
  -> exact owned-service status and resource observation
  -> user-service stop
  -> failed-state reset when required
  -> inactive/no-PID verification
  -> deterministic retirement of every unrevoked service grant
  -> durable successful outcome + typed report
```

Restart, regrant, reroute, and retry policy remain Core responsibilities. They
require a separate admitted operation after recovery succeeds.

## Operations

`terminate` accepts a typed reason and can stop an active, activating,
deactivating, or failed owned service. An already inactive service is idempotent,
but its remaining grants are still revoked. `UNKNOWN` is not treated as safe
terminal evidence.

`recover_failed` accepts only a service whose observed initial state is `FAILED`.
It stops the unit, invokes the provider-neutral failed-state reset port, and then
requires an inactive state with no main PID. Calling it for an active or inactive
service fails without a stop or grant change.

Both operations require a durable requested audit record before authorization or
adapter access. Denial, incomplete termination, and successful completion use
the same operation ID. Grant revocations retain their own nested audit operation
IDs and exact opaque resource IDs.

## systemd behavior

`systemctl stop` does not clear a systemd unit's failed state. The user-systemd
adapter therefore implements `ServiceFailureReset` with `systemctl --user
reset-failed`.

The default transient-service policy still uses `--collect`. Recovery-sensitive
services can explicitly select `retain_failed_state=True`, which emits
`CollectMode=inactive`. Failed state then remains observable until recovery,
while the unit is collected after it becomes inactive. No host system services
or global systemd settings are touched.

## Access cleanup

The grant registry returns unrevoked grants for one service in stable grant-ID
order. Safe termination first proves the process inactive, then revokes each
grant through the required-audit access controller. This prevents a later FAM
launch from reprojecting retired paths or devices.

If grant cleanup fails, no successful termination report is returned and the
outer operation records failure when the audit sink remains available. The
service remains inactive; callers must resolve cleanup before considering a
restart. Phase 3.7 threat tests cover bypass and partial-failure assumptions.

## Evidence boundary

`ServiceTerminationReport` is immutable and contains the initial and final typed
status, typed reason/disposition, sorted revoked grant IDs, and optional bounded
pre-stop resource snapshot. It rejects cross-service evidence, noninactive final
state, a retained main PID, and duplicate or unordered grant IDs.

The report does not claim that a process is gone based on a timeout, signal, or
`UNKNOWN` status. It also does not contain command lines, paths, exception text,
prompts, or model content.

## Evidence

Unit tests prove dedicated authorization, ownership, failed-only recovery,
idempotent inactive termination, unknown/nonterminal rejection, resource linkage,
sorted grant retirement, request-before-effect audit, and no restart after an
outcome-audit failure.

The opt-in live smoke creates a real user-systemd service that exits with code 7,
observes the retained `FAILED` state, runs stop plus reset-failed, verifies
`INACTIVE` with no PID, verifies two linked recovery audit records, and confirms
the private ledger mode.
