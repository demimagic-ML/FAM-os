# ADR 0004: Typed host inventory with a read-only Linux adapter

**Status:** Accepted  
**Date:** 2026-07-16

## Context

The parent RNF profiler returns a nested untyped dictionary and directly mixes Linux file reads, platform calls, disk inspection, NVIDIA command output, NPU device discovery, Ollama probing, timestamping, and JSON persistence.

FAM_OS scheduling policy needs hardware facts without depending on Linux paths, command output shapes, serialization, or Ollama. It must also distinguish physical host inventory from the effective cgroup resource limit proven necessary by the RNF experiments.

## Decision

The scheduler component owns an immutable provider-neutral `HardwareProfile` and the `HardwareDiscovery` port. Quantities use bytes or numeric SI values rather than provider-formatted strings. Runtime versions are generic `(runtime_id, version)` records instead of an Ollama-specific domain field.

The first adapter is `LinuxHardwareDiscovery`. It is read-only and composes small probes for:

- `/proc/meminfo` memory facts.
- `/proc/cpuinfo` CPU model facts.
- Standard-library OS, hostname, logical-CPU, timestamp, and root-filesystem facts.
- A bounded, shell-free `nvidia-smi` query.
- `/dev/accel/accel*` NPU device paths.
- A bounded, shell-free `ollama --version` query.

Missing optional probes degrade to unknown values or empty device collections. The adapter does not serialize or persist the profile. External wire schemas and compatibility policy remain Phase 2 work.

`HardwareProfile.memory` describes host inventory. It is never sufficient for model admission. Scheduling must later combine it with effective cgroup limits, current pressure, foreground workload, user policy, and reserved operating-system headroom.

## Consequences

- Scheduler policy can consume one typed profile independent of Linux or Ollama.
- Parser behavior is deterministic and fixture-tested without machine commands.
- Live hardware checks are opt-in and read-only.
- The profile can represent missing GPU, NPU, or runtime tools without failing discovery.
- Root-filesystem storage and NVIDIA GPU detail match Phase 1 prototype scope; broader device inventory can be added through additive contracts in Phase 2.
- Profile persistence must explicitly address hostname and device-identity privacy before being added.

## Alternatives considered

1. Move the parent dictionary function unchanged: rejected because it preserves provider coupling and implicit field types.
2. Let the Linux adapter return JSON dictionaries: rejected because serialization is not adapter or scheduler policy.
3. Treat host RAM as the runtime budget: rejected because the prototype proved Ollama can see host RAM while running inside a smaller cgroup ceiling.
4. Require every optional probe: rejected because CPU-only and partially provisioned systems must degrade safely.

## Evidence

- Fixture tests cover procfs, NVIDIA parsing, missing commands, typed validation, and complete adapter composition.
- The opt-in parity test matches the stable semantics of parent `rnf.profile.collect_profile` on the reference machine.
- Handoff 0004 records the current non-sensitive hardware smoke summary and exact validation commands.

