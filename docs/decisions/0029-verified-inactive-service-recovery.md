# ADR 0029: Recover services to a verified inactive baseline

**Status:** Accepted  
**Date:** 2026-07-16

## Context

Stopping an active process is not sufficient recovery evidence. A provider may
retain a failed control object, an ambiguous status may hide a running process,
and old filesystem/device grants could be projected by a later restart. Automatic
restart would also move retry and product policy into the deterministic
Supervisor boundary.

Live systemd testing showed that `--collect` can remove failure evidence before
recovery observes it, while `systemctl stop` alone leaves a retained unit in the
failed state.

## Decision

Define immutable termination reason, disposition, and report contracts. A
successful result requires exact owner and dedicated capability checks, a known
initial state, optional pre-stop resource evidence, an inactive final state with
no main PID, deterministic revocation of all unrevoked service grants, and linked
required audit records.

Define recovery as failed-to-inactive cleanup. It does not restart. Reject
recovery for a nonfailed initial state and reject `UNKNOWN` as terminal evidence.

Add a provider-neutral `ServiceFailureReset` port. Implement it in the user-
systemd adapter with `systemctl --user reset-failed`. Add an explicit
`retain_failed_state` setting that maps to `CollectMode=inactive`; keep the
existing `--collect` behavior as the default.

Mark failed-service recovery and safe owned-service termination as implemented
Supervisor capabilities.

## Consequences

- A recovery report is positive proof of inactive/no-PID state, not a request or
  timeout assumption.
- Failed state can be retained for diagnosis and then collected after recovery.
- All old access grants are retired before the operation reports success.
- Unknown status and partial cleanup fail closed.
- Restart, retry budget, fresh resource admission, and fresh grants stay in Core.
- Safe termination requires both its dedicated authority and the existing stop/
  access authorities used by the composed operation.
- A grant-cleanup failure leaves the service inactive but returns no successful
  report; reconciliation is required before restart.

## Alternatives considered

1. Treat `systemctl stop` as recovery: rejected because failed state remained.
2. Treat `UNKNOWN` as absent: rejected because the provider-neutral contract
   cannot distinguish absence from observation failure.
3. Restart automatically after cleanup: rejected because retry policy and fresh
   admission belong to Core.
4. Keep old grants for a convenient restart: rejected because stale authority
   must not survive recovery.
5. Disable transient collection globally: rejected because retention is needed
   only when failure diagnosis/recovery is selected.

## Evidence

- `src/fam_os/supervisor/recovery_contracts.py`
- `src/fam_os/supervisor/recovery.py`
- `src/fam_os/supervisor/ports/recovery.py`
- `src/fam_os/adapters/systemd/commands.py`
- `src/fam_os/adapters/systemd/lifecycle.py`
- `tests/unit/test_service_recovery.py`
- `tests/hardware/service_recovery_smoke.py`
