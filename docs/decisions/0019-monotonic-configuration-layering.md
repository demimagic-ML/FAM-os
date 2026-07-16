# ADR 0019: Trusted profile replacement with monotonic user and session restrictions

**Status:** Accepted  
**Date:** 2026-07-16

## Context

FAM_OS has provider-neutral inventory and effective-budget contracts but no deterministic rule for combining defaults, live host/cgroup facts, the selected validation profile, user preferences, and temporary session limits. Direct dictionary merging would let a late layer accidentally enable a GPU, reduce operating-system headroom, exceed a cgroup, or reinterpret SSD as memory.

The safe fallback and the full workstation also have intentionally different authority. If every layer were restriction-only, conservative defaults could never be replaced by the trusted full-workstation profile. If every layer were replacement-capable, user or session input could expand authority.

## Decision

FAM_OS distinguishes complete trusted policies from untrusted or weaker restrictions.

`SchedulerDefaults` and `ValidationProfileConfiguration` contain complete `ResourcePolicy` values. One admitted named profile may replace the defaults. Both remain subordinate to discovered physical capacity and enforcement limits.

`UserResourcePolicy` and `SessionResourceOverride` contain only `ResourceRestriction`. Maximums compose with `min`, minimum reserves with `max`, and accelerator permission with logical `AND`. A looser requested value cannot expand the selected policy. Session restrictions are time-bound and inactive documents are ignored with an audit record.

Pure deterministic composition produces an existing `EffectiveResourceBudget` plus ordered structured decisions. Discovery remains a read-only input and is applied as a hard final clamp. Composition performs no probe, cgroup mutation, model selection, service start, or provider call.

CPU allocation reserves deterministic logical IDs. RAM is bounded by host and cgroup capacity with explicit headroom. Accelerator VRAM and storage cache remain separate domains. Storage cache derives from available storage and cache eligibility and is never added to memory.

The configuration family is `fam.configuration/v1alpha1` and adds seven strict schema-catalog roots. The compatibility rules of ADR 0018 apply unchanged.

## Consequences

- The full workstation can deliberately enable resources that conservative defaults leave disabled.
- User and session controls can always reduce resource use but cannot create authority or capacity.
- Cgroup/host facts clamp every trusted desired value.
- Expired session state cannot silently remain effective.
- Over-budget current use remains visible for recovery.
- Every composition explains selection, restriction, ignored expansion, and physical clamp decisions.
- Concrete profile capacities remain Phase 2.11 data rather than hard-coded composer behavior.
- Later per-device, battery, thermal, or predictive policies require a new schema version if they change public meaning.

## Alternatives considered

1. Generic last-write-wins merging: rejected because precedence would also become authority escalation.
2. Make every layer restriction-only: rejected because a trusted full-workstation profile could not replace conservative fallback values.
3. Let user/session documents contain full policies: rejected because omitted fields and permissive values could accidentally enable resources.
4. Apply discovery first and mutate its values through later layers: rejected because it makes it easier for a later layer to escape a physical or cgroup ceiling.
5. Put machine-specific byte values and GPU IDs in the composer: rejected because Phase 2.11 owns profile data and adapters own discovery.
6. Treat available SSD bytes as extra memory: rejected because storage has different latency, persistence, transfer, and failure semantics.
7. Have the composer enforce cgroups directly: rejected because the scheduler chooses policy while the supervisor and adapters enforce it.

## Evidence

- `docs/protocols/CONFIGURATION_LAYERING.md`
- `src/fam_os/scheduler/configuration/`
- `tests/unit/test_configuration_layering.py`
- Configuration roots in `src/fam_os/schemas/catalog.py`
- Generated `fam.configuration.*` artifacts under `schemas/v1alpha1/`
- ADR 0011, ADR 0015, and ADR 0018
