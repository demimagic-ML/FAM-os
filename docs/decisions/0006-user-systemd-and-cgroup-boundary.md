# ADR 0006: User-systemd lifecycle and read-only cgroup observation

**Status:** Accepted  
**Date:** 2026-07-16

## Context

The RNF prototype proves that a transient Ollama server can run CPU-only under a 16 GiB memory ceiling with swap disabled. Its shell script directly mixes service lifecycle, environment configuration, cgroup limits, readiness polling, and application-specific Ollama details. Its experiment code separately mixes `systemctl show`, cgroup-v2 file parsing, report construction, and scheduling evidence.

FAM_OS needs to preserve the proven enforcement and telemetry without making Core, the scheduler, or the future privileged supervisor depend on systemd commands, cgroup paths, shell behavior, or model-specific readiness checks.

## Decision

The supervisor component owns immutable provider-neutral contracts for:

- Service definitions, lifecycle state, and status.
- Memory, swap, CPU-quota, and task-count limits.
- Memory and swap observations, finite or unbounded ceilings, resource events, and pressure samples.
- `ServiceLifecycle` and `ResourceObserver` ports.

The first lifecycle adapter is `SystemdUserServiceLifecycle`. It supports only user-scoped transient services, invokes `systemd-run --user` and `systemctl --user` without a shell, applies approved limits as unit properties, and collects transient units after exit. Command names and timeouts are explicit settings. The adapter reports lifecycle state but does not poll application endpoints or interpret readiness.

The first resource adapter is `CgroupV2ResourceObserver`. It resolves an opaque service resource group through an injected locator and reads the cgroup-v2 memory controller directly. It never writes controller files. Missing units, groups, or individual optional files degrade safely. Present but malformed controller data raises the stable `ResourceObservationError` boundary.

An absent ceiling is distinct from an explicit unbounded ceiling. `ResourceSnapshot.memory_limit is None` means unavailable; `ResourceCeiling(None)` means the controller explicitly reported `max`.

Phase 1 enforcement remains delegated to systemd transient-unit properties. Direct cgroup mutation, privileged system services, authorization, durable unit installation, readiness policy, and scheduling decisions remain outside this adapter migration.

## Consequences

- The 16 GiB/no-swap prototype policy can be expressed without a model-specific shell script.
- Core and scheduler code can fake lifecycle and resource observation without systemd or Linux.
- Systemd and cgroup-v2 can be replaced independently.
- A cgroup observer can consume a systemd locator without importing systemd output into supervisor contracts.
- Generic lifecycle success does not imply application readiness; a later use case must own bounded health checks.
- Environment values currently travel as transient-unit arguments. Callers must not use this path for secrets; a credential transport requires a separate security decision.
- Phase 3 must add authorization, audit emission, failure recovery, and a hardened privilege boundary before these mechanics become a production supervisor.

## Alternatives considered

1. Copy `scripts/rnf-cpu-server`: rejected because it mixes Ollama readiness, environment, lifecycle, and resource policy in a god script.
2. Put systemd commands in Core or scheduler code: rejected because operating-system mechanisms must remain replaceable adapters.
3. Read resource values only from `systemctl show`: rejected because pressure and event counters live in cgroup controller files and systemd is not the resource model.
4. Write cgroup files directly in Phase 1: rejected because systemd already owns these transient service cgroups and direct writes would introduce authority and ownership conflicts.
5. Treat missing and `max` limits as the same value: rejected because admission policy must distinguish unknown capacity from explicitly unbounded capacity.

## Evidence

- Fixture tests cover contract validation, exact command construction, lifecycle status mapping, finite and unbounded limits, event counters, pressure parsing, missing-controller degradation, and malformed-controller errors.
- The opt-in live test starts a short-lived user service with 64 MiB memory, zero swap, 25 percent CPU quota, and an eight-task ceiling; observes its cgroup values; and removes it in cleanup.
- Handoff 0006 records the exact suite, live validation, cleanup result, and parent regression result.
