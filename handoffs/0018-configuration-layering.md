# Handoff 0018: Deterministic configuration layering

**Date:** 2026-07-16  
**Plan step:** Phase 2.8  
**Status:** Complete  
**Previous handoff:** `0017-strict-schema-compatibility.md`

## Objective

Define and implement deterministic composition across safe defaults, read-only discovered/enforced capacity, one trusted named validation profile, user restrictions, and time-bounded session restrictions without letting a weaker layer expand resource authority.

## Scope completed

- Added the `fam.configuration/v1alpha1` contract family.
- Added a complete provider-neutral `ResourcePolicy` for trusted safe defaults and admitted validation profiles.
- Added a separate partial `ResourceRestriction` shape for user and session layers.
- Added versioned scheduler-default, validation-profile, user-policy, and session-override roots.
- Added versioned discovered resource state joining `HostInventory` to cgroup CPU/RAM, service swap, current RAM/VRAM/cache, and pressure facts.
- Required discovered accelerator and storage runtime IDs to exist in the captured inventory.
- Added deterministic policy selection where a trusted named profile may replace defaults.
- Applied user and session maximums with `min`, minimum reserves with `max`, and accelerator authority with logical `AND`.
- Prevented a looser user/session request from expanding the selected policy and recorded it as ignored.
- Applied session restrictions only inside their aware, exclusive validity window and audited inactive overrides.
- Added pure deterministic CPU, RAM/swap, accelerator, and storage budget builders.
- Clamped all desired values to physical inventory, current availability, and known cgroup ceilings.
- Preserved over-budget current usage instead of inflating limits or hiding pressure.
- Kept SSD cache separate from system RAM and accelerator VRAM.
- Added ordered configuration decisions for selected, overridden, restricted, clamped, and ignored values.
- Produced the existing `EffectiveResourceBudget` as the composed scheduler authority.
- Registered seven new strict wire roots and generated their Draft 2020-12 artifacts, raising the catalog from 27 to 34 roots.
- Added focused contract, composition, monotonicity, expiry, cgroup, GPU, SSD, determinism, and invalid-input tests.
- Added protocol documentation, ADR 0019, ownership documentation, and Master Plan updates.

## Explicitly not completed

- No concrete `compat-cpu-16gb` or `full-reference-workstation` configuration document was added; that is Phase 2.11.
- No hardware or cgroup probe was invoked and no adapter was changed to create `DiscoveredResourceState` from the live machine.
- No cgroup, systemd unit, GPU visibility, I/O controller, or process limit was mutated.
- No benchmark service composition consumes the selected profile yet; that is Phase 2.12.
- No expert placement, context sizing, eviction, prefetch, thermal, battery, or foreground-load policy was implemented.
- No user settings UI or session-policy client was added.
- No untrusted source is automatically promoted to a trusted validation profile.

## Architecture and decisions

ADR 0019 separates replacement authority from restriction authority. `SchedulerDefaults` and `ValidationProfileConfiguration` are complete trusted inputs. An admitted named profile can replace conservative fallback values so a full workstation is not trapped by CPU-only defaults. `UserResourcePolicy` and `SessionResourceOverride` cannot replace the selected policy; their type contains only monotonic restrictions.

Discovery supplies a hard ceiling rather than a writable layer. It is applied after desired policy composition, so neither the trusted profile nor later restrictions can exceed host/cgroup capacity. The composer does not perform discovery itself and cannot enforce its result.

CPU selection is deterministic: logical IDs are sorted and the configured number of highest IDs is reserved. RAM uses the smaller host/cgroup ceiling and always subtracts explicit headroom. Accelerator placement requires policy authority, known device memory, and positive VRAM after reserve. Storage cache uses current available storage and cache eligibility and is never summed with memory.

The output combines the already versioned `EffectiveResourceBudget` with ordered `ConfigurationDecision` evidence. Audit decisions explain policy; they are not telemetry and do not claim supervisor enforcement.

The implementation remains modular. The largest new module is `configuration/builders.py` at 169 lines. All implementation modules remain below 300 lines and all functions remain below 50 lines.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/scheduler/configuration/policy.py` | Complete trusted policies and partial restriction roots |
| `src/fam_os/scheduler/configuration/discovery.py` | Inventory-linked enforcement/current-use state |
| `src/fam_os/scheduler/configuration/audit.py` | Ordered decision vocabulary |
| `src/fam_os/scheduler/configuration/layering.py` | Profile selection, monotonic restrictions, and session expiry |
| `src/fam_os/scheduler/configuration/builders.py` | Physical/cgroup CPU, RAM, VRAM, and storage clamps |
| `src/fam_os/scheduler/configuration/composer.py` | Pure composition request, result, and use case |
| `src/fam_os/scheduler/configuration/__init__.py` | Public configuration exports |
| `src/fam_os/scheduler/configuration/README.md` | Local ownership and dependency boundary |
| `src/fam_os/scheduler/__init__.py` | Scheduler-level public configuration exports |
| `src/fam_os/schemas/catalog.py` | Seven configuration document registrations |
| `schemas/v1alpha1/fam.configuration.*.schema.json` | Generated strict configuration artifacts |
| `tests/unit/test_configuration_layering.py` | Contract, precedence, resource, and audit behavior |
| `tests/contract/schema_configuration_fixtures.py` | Representative values for all seven roots |
| `tests/contract/test_schema_roundtrip.py` | Catalog completeness extended to 34 roots |
| `docs/protocols/CONFIGURATION_LAYERING.md` | Layer semantics, composition equations, and boundaries |
| `docs/protocols/SERIALIZED_SCHEMA_COMPATIBILITY.md` | Current schema count and ADR coverage |
| `docs/protocols/HARDWARE_RESOURCE_CONTRACTS.md` | Composition link from budget contracts |
| `docs/decisions/0019-monotonic-configuration-layering.md` | Authority and precedence decision |
| `src/fam_os/scheduler/README.md` | Scheduler configuration ownership |
| `README.md` | Current implementation and next-step status |
| `MASTER_PLAN.md` | Phase 2.8 completion and Phase 2.11 entry point |
| `handoffs/README.md` | Handoff sequence entry |
| `handoffs/0018-configuration-layering.md` | This implementation record |

## Public interfaces

- `CONFIGURATION_CONTRACT_VERSION`
- `ResourcePolicy`
- `ResourceRestriction`
- `SchedulerDefaults`
- `ValidationProfileConfiguration`
- `UserResourcePolicy`
- `SessionResourceOverride`
- `AcceleratorRuntimeState`
- `StorageRuntimeState`
- `DiscoveredResourceState`
- `ConfigurationLayer`
- `ConfigurationDecisionKind`
- `ConfigurationDecision`
- `ConfigurationCompositionRequest`
- `ComposedResourceConfiguration`
- `compose_resource_configuration`

## Validation

```bash
cd <REPO_ROOT>/FAM_OS
PYTHONPATH=src:. python3 -m unittest tests.unit.test_configuration_layering
```

Result: all 15 focused configuration tests passed in 0.001 seconds; 0 failures.

```bash
PYTHONPATH=src:. python3 -m unittest \
  tests.contract.test_schema_roundtrip \
  tests.contract.test_schema_compatibility \
  tests.contract.test_cross_contract_references
```

Result: all 23 focused schema tests passed in 0.113 seconds; 0 failures. Every one of the 34 registered roots has a representative canonical round trip.

```bash
PYTHONPATH=src:. python3 -m unittest discover -s tests
```

Result: all 231 FAM_OS tests passed in 0.161 seconds; 0 failures. The previous suite contained 216 tests.

```bash
PYTHONPATH=src:. python3 tools/render_contract_schemas.py --check
```

Result: all 34 generated schema artifacts exactly match the catalog and domain annotations.

```bash
python3 -m compileall -q src tools tests
```

Result: completed successfully.

```bash
rg -n "Ollama|ollama|systemd|subprocess|vscode|WorkspaceEdit|MCP|mcp" \
  src/fam_os/scheduler/configuration
```

Result: no inference provider, service manager, subprocess, editor SDK, or connector protocol dependency was found.

An AST audit found no implementation module at or above 300 lines and no function at or above 50 lines.

## Evidence and artifacts

- `docs/protocols/CONFIGURATION_LAYERING.md`
- `docs/decisions/0019-monotonic-configuration-layering.md`
- `tests/unit/test_configuration_layering.py`
- `tests/contract/schema_configuration_fixtures.py`
- `schemas/v1alpha1/fam.configuration.*.schema.json`
- Dual-profile decision: ADR 0011
- Inventory/budget decision: ADR 0015
- Strict schema decision: ADR 0018

## Known limitations and risks

- Trust admission for `ValidationProfileConfiguration` is outside the pure composer. Callers must never treat arbitrary user/session input as a trusted profile.
- The alpha policy applies one generic accelerator policy and one generic storage policy across discovered devices. Per-device policy will require an explicit future schema.
- Reserving the highest CPU IDs is deterministic but topology-oblivious; NUMA, hybrid performance/efficiency cores, affinity, and foreground ownership remain Phase 7 concerns.
- Storage effective cache capacity uses one captured available-byte value. Live admission must recapture state and handle concurrent filesystem use.
- A runtime-state entry omitted for a known accelerator or storage tier defaults current FAM use to zero; production adapters must provide complete measured state when admission depends on it.
- Audit requested/effective values are safe strings for explanation, not signed evidence or high-frequency metrics.
- Composition validates a snapshot and cannot prove the supervisor applied the resulting cgroup/device/I/O constraints.
- An excessive user/session minimum reserve can make composition fail. This is intentional fail-closed behavior, but UI remediation does not yet exist.
- Phase 1 `ResourceBudget` remains in parallel until profile-driven runtime composition is migrated and parity-tested.

## Operational notes

This change is immutable contracts, pure in-memory composition, generated schemas, documentation, and tests. It performed no live discovery, hardware allocation, model loading, service start, cgroup mutation, connector action, or persistent configuration write.

## Recommended next entry point

Begin Phase 2.11. Create checked serialized `ValidationProfileConfiguration` documents for `compat-cpu-16gb` and `full-reference-workstation`. Keep reusable desired policy separate from the time-varying, privacy-reviewed `DiscoveredResourceState`. Decode both profiles through `fam_os.schemas`, compose them against deterministic inventory/enforcement fixtures, prove the compatibility profile has a 16 GiB service ceiling, zero swap, and no accelerator placement, and prove the full profile exposes CPU, RAM, VRAM, and NVMe without an artificial 16 GiB cap.
