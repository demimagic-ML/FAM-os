# FAM Supervisor capability boundary

## Role

The FAM Supervisor is the smallest deterministic operating-system control boundary. It accepts already-authorized, typed service intent; validates that intent; delegates bounded operations to operating-system adapters; and returns typed status and measurements.

It is not an intelligence process and it is not Linux kernel code.

```text
authenticated FAM Core caller
  -> typed supervisor operation
  -> deterministic validation
  -> user-session OS adapter
  -> service status/resource evidence/audit result
```

## Current capabilities

The canonical `SupervisorBoundary` records capabilities already proven through Phase 1 and Phase 2 adapters:

- start one declared unprivileged user-session service;
- stop an owned user-session service;
- read owned service status;
- apply declared CPU, RAM, swap, and task limits at service creation;
- observe owned service CPU, RAM, swap, I/O, pressure, and resource events when the controller exposes them.
- grant allowlisted, expiring filesystem and device access to an exact owned service.
- emit required, privacy-bounded audit records into a durable hash-chained ledger.
- recover a failed owned service to verified inactive state and safely terminate
  an owned service while retiring its access grants.

Current implementations use user-scoped systemd transient services and read-only cgroup-v2 observation. These adapters are mechanisms, not authorization. Until Phase 3 adds an authenticated supervisor entrypoint, only trusted in-process composition may call them.

## Planned supervisor capabilities

The Phase 3 boundary currently has no declared-but-unimplemented capability.
Later additions require a new plan step and decision record; an empty planned set
does not authorize an adapter to invent operations.

## Caller and ownership assumptions

- Every production caller must be authenticated before supervisor admission.
- The caller must carry a user-session principal and an explicit service ownership scope.
- Start authority does not imply stop/status/observe authority over arbitrary processes.
- Service IDs are FAM-owned identifiers, not a way to address arbitrary systemd units.
- Unknown ownership, missing measurement, or ambiguous authorization must fail closed.
- Core decides why a service is needed; the Supervisor only validates and applies already-selected intent.

Phase 3.4 turns ownership into opaque capability grants and a real mount-namespace projection. Phase 3.5 makes audit writes a required part of the lifecycle, resource-limit, and access compositions. External authentication transport remains future work; current composition injects the authorizer.

Phase 3.6 adds failed-state reset and safe termination. It returns services to a
verified inactive/no-PID state and retires old access grants; it never decides to
restart them.

## Explicit non-goals

The supervisor never owns:

- model inference or prompt interpretation;
- routing, planning, memory retrieval, or content verification;
- application decisions or desktop actions;
- arbitrary process control or system-service administration;
- credentials or secret management;
- package or model installation.

Those exclusions are represented by `SupervisorNonGoal` and guarded by `SupervisorBoundary` invariants. The boundary cannot disable authenticated-caller requirements or enable system service/model authority.

## Privilege model

Unprivileged user-session operation is the default and current implementation. Future privileged helpers, if any capability truly requires one, must be separately deployed, narrowly callable, allowlisted, audited, and unable to import model/Core/Application logic. Phase 3 must not turn the existing user-systemd adapter into a general root service manager.

## Relationship to later phases

- FAM Core owns request state, planning, approval, verification, and release.
- Application Fabric owns permissioned observations and actions.
- Expert Fabric owns model packages and fitness.
- Scheduler owns resource allocation policy.
- Supervisor owns deterministic enforcement and evidence only.
