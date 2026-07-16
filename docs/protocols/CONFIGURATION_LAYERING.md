# Scheduler Configuration Layering Protocol

## Contract family

Scheduler configuration documents use `fam.configuration/v1alpha1`. Seven public roots are registered with the strict schema catalog:

- scheduler safe defaults;
- named validation-profile configuration;
- user resource policy;
- session resource override;
- discovered resource state;
- configuration composition request;
- composed resource configuration.

All roots use the exact-match wire, unknown-field, enum, timestamp, and domain-validation rules in `SERIALIZED_SCHEMA_COMPATIBILITY.md`.

## Precedence and authority

Composition uses one deterministic order:

```text
complete safe defaults
  -> trusted named profile replacement
  -> user restriction
  -> active session restriction
  -> discovered host and enforcement clamps
  -> EffectiveResourceBudget + decisions
```

Discovery is listed second in the conceptual configuration sources because it supplies the hard machine boundary. It is applied as the final clamp so no desired value from any policy layer can escape the captured host/cgroup ceiling.

A trusted named profile may replace the defaults. This is necessary for `full-reference-workstation` to enable accelerators and larger budgets while the safe fallback can remain conservative. Profile selection is an admitted system configuration operation, not an end-user override.

User and session documents are `ResourceRestriction` values, not complete replacement policies. Their algebra is monotonic:

- maximum CPU, RAM, swap, VRAM, cache, and I/O values use `min`;
- minimum RAM, VRAM, and storage reserves use `max`;
- accelerator permission uses logical `AND`;
- a missing restriction leaves the current value unchanged;
- a requested looser value is ignored and audited as `no_authority_expansion`.

Session restrictions apply only from `issued_at` until the exclusive `expires_at`. An inactive session document is ignored and produces an explicit audit decision.

## Complete resource policy

`ResourcePolicy` is used only by safe defaults and trusted profiles. It declares provider-neutral ratios, optional absolute ceilings, and explicit reserves for:

- CPU quota and logical CPUs reserved for Linux and foreground work;
- scheduler RAM, RAM headroom, and service swap;
- accelerator placement, schedulable memory, and reserved accelerator memory;
- storage cache, free-space reserve, and optional read/write ceilings.

It contains no model name, GPU index, mount path, cgroup path, command, Ollama option, or systemd property. The same policy can compose against a fake inventory, the minimum profile, or a recaptured workstation.

## Discovered resource state

`DiscoveredResourceState` combines an immutable `HostInventory` with enforcement and current-use facts needed for one composition:

- optional cgroup CPU quota;
- optional cgroup memory limit;
- current service memory;
- service swap limit and current swap;
- current per-accelerator memory;
- current per-storage FAM cache bytes;
- normalized pressure readings.

Runtime accelerator and storage IDs must exist in the inventory. Discovery is read-only data; it grants no allocation authority and performs no hardware probe itself.

## Composition rules

CPU IDs are sorted for deterministic selection. The configured number of highest logical IDs is reserved, and the remainder is schedulable. CPU quota is the smallest of the policy fraction, optional policy maximum, schedulable CPU count, and cgroup quota.

Effective RAM is the smaller of physical RAM and a known cgroup memory limit. Scheduler RAM is the smallest of the policy fraction, optional policy maximum, and effective RAM minus required headroom. A headroom value that leaves no positive scheduler capacity fails composition rather than creating an unusable budget.

Accelerator placement requires all of:

- the selected profile permits acceleration;
- the user/session restrictions do not disable it;
- inventory reports accelerator memory;
- a positive schedulable memory budget remains after the reserve.

The `compat-cpu-16gb` profile contract rejects accelerator permission before composition. A physically visible GPU can still appear in the output with placement disabled and zero schedulable VRAM.

Storage cache capacity is computed from the storage tier's current available bytes, policy ratio/maximum, and reserved free space. A non-cache-eligible tier receives zero schedulable cache. Storage bytes are never added to RAM or VRAM.

Current memory, swap, VRAM, or cache use may exceed a newly reduced scheduler ceiling. The composed budget preserves that observation so recovery and admission can see the unsafe state; it does not hide the excess by inflating the limit.

## Audit decisions

`ComposedResourceConfiguration` contains the `EffectiveResourceBudget` and ordered `ConfigurationDecision` records. Each decision names:

- layer and source ID;
- setting;
- requested and effective values;
- selected, overridden, restricted, clamped, or ignored disposition;
- stable reason code.

This trace explains profile replacement, monotonic restrictions, inactive sessions, and discovery clamps. It is policy evidence, not telemetry measurement and not proof that the supervisor enforced the result.

## Phase boundaries

- Phase 2.8 defines contracts and pure deterministic composition only.
- Phase 2.11 supplies concrete versioned values for the two required named profiles in `configs/profiles/`; see `VALIDATION_PROFILE_DOCUMENTS.md` and ADR 0020.
- Phase 2.12 consumes the selected profile in benchmark service composition.
- Phase 3 and Phase 7 implement enforcement and live scheduling behavior.
- Hardware probes remain in adapters, and no configuration document can execute a probe or mutate a cgroup.

## Known limits

The alpha policy applies one generic accelerator and storage policy across discovered devices. Per-device classes, thermal/battery policy, foreground load, placement cost, and predictive behavior belong to later scheduler phases. A future schema must add those meanings under a new version rather than silently extending `v1alpha1`.
