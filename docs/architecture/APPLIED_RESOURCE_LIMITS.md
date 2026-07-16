# Applied resource-limit verification

## Invariant

A service is not considered constrained merely because FAM requested limits or constructed a valid systemd command. `ConstrainedServiceLifecycle` reports `constrained=True` only after observing the service cgroup and exactly matching every requested ceiling.

The verified resource set is:

- `memory.max` against requested memory bytes;
- `memory.swap.max` against requested swap bytes;
- `cpu.max` quota/period against requested CPU percentage;
- `pids.max` against requested task count.

## Evidence states

Each resource produces one `AppliedLimitCheck`:

- `matched`: requested and observed finite values match;
- `mismatched`: a different value or explicit unbounded ceiling was observed;
- `unavailable`: the snapshot/controller field was absent;
- `not_requested`: the definition did not request that limit.

Explicit `max` and missing data are not equivalent. A constrained result requires at least one requested/matched limit and permits only `matched` or `not_requested` checks.

## Rollback

`ConstrainedServiceLifecycle.start` requires both start and resource-limit authority, starts through `OwnedServiceLifecycle`, observes through `ResourceObserver`, and verifies the exact limits. If verification fails, it immediately issues a compensating stop through the already-owned raw lifecycle adapter and returns an outcome with `constrained=False` plus cleanup status and complete evidence.

The internal compensating stop does not require caller stop authority because it removes a service that the same admitted start just created but could not prove safe. General recovery and retry remain Phase 3.6.

## Adapter ownership

- Supervisor owns requested-versus-applied policy and outcome.
- Systemd adapter owns translation to user-service properties.
- Cgroup adapter owns controller parsing and observation.
- Scheduler chooses the resource budget before Supervisor admission.

No direct cgroup file mutation is used; systemd remains the cgroup owner.
