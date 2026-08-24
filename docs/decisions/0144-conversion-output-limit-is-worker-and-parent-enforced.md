# ADR 0144: Conversion output limits are enforced by worker and parent

Status: Accepted

## Context

The conversion sandbox runs in a transient systemd scope so the caller can
monitor and terminate the exact worker process while cgroups enforce memory,
swap, CPU, task, and runtime limits. `LimitFSIZE` is an execution property, not
a supported scope resource-control property. Passing it to `systemd-run
--scope` caused the physical converter to exit before Bubblewrap launched.

The approved output-byte limit was already independently present in the private
worker configuration and in the parent monitor. The worker checks the output
directory after each conversion stage and before success; the parent samples it
while the subprocess is active, terminates an over-budget scope, validates the
terminal directory size, and discards failed outputs.

## Decision

Do not pass unsupported `LimitFSIZE` to the transient scope. Keep output-byte
enforcement at both supported boundaries: the untrusted isolated worker and the
trusted parent backend. Continue using the scope for supported cgroup and
runtime controls.

## Consequences

- Physical conversion can enter the network-denied Bubblewrap sandbox.
- Output bytes remain approval-bound and independently checked on both sides of
  the sandbox boundary.
- A transient overshoot can exist for at most one parent sampling interval;
  failed or oversized outputs are removed and cannot produce a completed
  receipt.
- Systemd scope properties are limited to properties the host actually accepts.

## Alternatives considered

- Keeping `LimitFSIZE` was rejected because the host deterministically refuses
  the transient scope.
- Running an unsupervised worker was rejected because it would lose cgroup and
  parent-side enforcement.
- Converting through a transient service was deferred because it changes
  process ownership, output capture, and cancellation semantics without adding
  protection beyond the existing dual byte checks.

## Evidence

- `src/fam_os/adapters/training/isolated_conversion_command.py`
- `src/fam_os/adapters/training/conversion_worker.py`
- `src/fam_os/adapters/training/llama_cpp_conversion_backend.py`
- `tests/unit/test_factory_conversion_isolation.py`
