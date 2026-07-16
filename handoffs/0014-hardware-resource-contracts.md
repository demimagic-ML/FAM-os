# Handoff 0014: Hardware inventory and effective resource contracts

**Date:** 2026-07-16  
**Plan step:** Phase 2.2  
**Status:** Complete  
**Previous handoff:** `0013-core-execution-plan-contracts.md`

## Objective

Define versioned, provider-neutral schemas for physical host inventory and the effective resources FAM may schedule, including CPU allocation, RAM and cgroup limits, explicit operating-system headroom, GPU VRAM, SSD cache/I/O budgets, current pressure, and the distinction between the two required validation profiles.

## Scope completed

- Added `fam.hardware.inventory/v1alpha1` as the host-inventory contract family.
- Added typed CPU topology, physical memory/swap, accelerator, and storage-tier inventory.
- Added `fam.hardware.budget/v1alpha1` as the effective-resource-budget family.
- Added visible, schedulable, and reserved logical CPU sets plus scheduler and cgroup quotas.
- Added effective RAM, scheduler RAM, reserved headroom, current RAM, cgroup RAM, and service-swap fields.
- Added per-accelerator placement authority, effective VRAM, schedulable VRAM, reserved VRAM, and current VRAM.
- Added per-storage effective cache, scheduler cache, reserved free space, current cache, and optional read/write rate budgets.
- Added timezone-aware normalized utilization/stall pressure readings tied to known resource IDs.
- Added stable profile identity and purpose contracts for `compat-cpu-16gb`, `full-reference-workstation`, and custom profiles.
- Prevented the compatibility profile from allowing accelerator placement while permitting it to record a physically visible but disallowed GPU.
- Preserved over-budget current usage so pressure and recovery paths can observe it; new RAM availability becomes zero.
- Kept SSD/cache, system RAM, and VRAM as distinct resource domains.
- Kept the Phase 1 Linux `HardwareProfile`, per-expert `ResourceBudget`, discovery adapter, and scheduler behavior unchanged.
- Added protocol documentation, ADR 0015, unit tests, scheduler ownership documentation, and plan/status updates.

## Explicitly not completed

- No JSON or other wire encoder/decoder was added; serialized schema compatibility is Phase 2.7.
- No Linux hardware adapter was migrated to emit `HostInventory`.
- No cgroup, NVIDIA, storage, or pressure adapter was changed.
- No policy composes host discovery, cgroup state, named profile, user policy, or session overrides into an effective budget; that is Phase 2.8.
- No concrete `compat-cpu-16gb` or `full-reference-workstation` configuration document was created; that is Phase 2.11.
- No benchmark composition or GPU-enabled service was changed.
- No scheduler admission, placement, eviction, or enforcement behavior changed.

## Architecture and decisions

ADR 0015 separates physical discovery from scheduling authority. `HostInventory` says what exists; `EffectiveResourceBudget` says what is visible, reserved, and schedulable at a timestamp. This prevents host RAM, visible GPUs, or free SSD space from becoming implicit permission.

Each bounded resource distinguishes an effective ceiling from a scheduler ceiling and an explicit reserve. RAM additionally records a cgroup ceiling and service swap. CPU records exact visible/schedulable/reserved IDs and optional cgroup quota. VRAM and storage cache use their own fields and are never added to RAM.

Current usage is allowed to exceed a newly reduced scheduler ceiling. Rejecting such a snapshot would hide precisely the state that recovery and telemetry need to observe. The available-for-new-memory calculation clamps to zero.

The two reserved validation-profile names have fixed semantic purposes. The compatibility identity has a schema-level accelerator prohibition. Exact capacities and headroom remain data for Phase 2.11 rather than machine-specific constants in domain code.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/scheduler/resources/identity.py` | Reserved validation-profile IDs, purposes, and identity validation |
| `src/fam_os/scheduler/resources/inventory.py` | Versioned CPU, RAM, accelerator, storage, and host inventory contracts |
| `src/fam_os/scheduler/resources/pressure.py` | Normalized timestamped resource-pressure readings |
| `src/fam_os/scheduler/resources/budget.py` | CPU, RAM, VRAM, cache/I/O, and effective-budget contracts |
| `src/fam_os/scheduler/resources/__init__.py` | Public resource-contract exports |
| `src/fam_os/scheduler/__init__.py` | Scheduler package exports |
| `tests/unit/test_host_inventory_schema.py` | Host schema and physical-tier invariants |
| `tests/unit/test_effective_resource_budget_schema.py` | Effective limits, headroom, pressure, and profile-separation tests |
| `docs/protocols/HARDWARE_RESOURCE_CONTRACTS.md` | Contract-family semantics and invariants |
| `docs/decisions/0015-host-inventory-effective-resource-budgets.md` | Durable separation and budgeting decision |
| `docs/architecture/HARDWARE_VALIDATION_PROFILES.md` | Phase 2.2 implementation link |
| `src/fam_os/scheduler/README.md` | Scheduler ownership and compatibility boundary |
| `MASTER_PLAN.md` | Phase 2.2 completion evidence and Phase 2.3 entry point |
| `README.md` | Current capability and next-step status |
| `handoffs/README.md` | Handoff sequence entry |
| `handoffs/0014-hardware-resource-contracts.md` | This implementation record |

## Public interfaces

- `HOST_INVENTORY_CONTRACT_VERSION`
- `EFFECTIVE_RESOURCE_BUDGET_CONTRACT_VERSION`
- `COMPAT_CPU_16GB_PROFILE_ID`
- `FULL_REFERENCE_WORKSTATION_PROFILE_ID`
- `ValidationProfilePurpose`
- `ValidationProfileRef`
- `AcceleratorKind`
- `StorageMedium`
- `HostCpuInventory`
- `HostMemoryInventory`
- `HostAcceleratorInventory`
- `HostStorageInventory`
- `HostInventory`
- `PressureReading`
- `CpuResourceBudget`
- `MemoryResourceBudget`
- `AcceleratorResourceBudget`
- `StorageResourceBudget`
- `EffectiveResourceBudget`

Existing `HardwareProfile`, `HardwareDiscovery`, `ResourceBudget`, and `PlacementPlan` interfaces remain unchanged.

## Validation

```bash
cd <REPO_ROOT>/FAM_OS
PYTHONPATH=src:. python3 -m unittest \
  tests.unit.test_host_inventory_schema \
  tests.unit.test_effective_resource_budget_schema -v
```

Result: all 22 focused hardware-inventory and effective-budget tests passed in 0.001 seconds; 0 failures.

```bash
cd <REPO_ROOT>/FAM_OS
PYTHONPATH=src:. python3 -m unittest discover -s tests -v
```

Result: all 156 FAM_OS tests passed in 0.034 seconds; 0 failures. The previous suite contained 134 tests.

```bash
python3 -m compileall -q src tools tests
```

Result: completed successfully.

```bash
rg -n "Ollama|nvidia-smi|subprocess|systemd|MCP|vscode" \
  src/fam_os/scheduler/resources
```

Result: no inference runtime, Linux command, process, service, MCP, or editor dependency was found.

```bash
find src/fam_os -name '*.py' -print0 | xargs -0 wc -l | sort -nr | head -n 12
```

Result: `scheduler/resources/budget.py` is 198 lines and `inventory.py` is 141 lines. All new implementation modules are below the repository's 300-line target; their functions remain below the 50-line target.

## Evidence and artifacts

- `docs/protocols/HARDWARE_RESOURCE_CONTRACTS.md`
- `docs/decisions/0015-host-inventory-effective-resource-budgets.md`
- `tests/unit/test_host_inventory_schema.py`
- `tests/unit/test_effective_resource_budget_schema.py`
- Hardware-profile decision: `docs/decisions/0004-read-only-hardware-discovery.md`
- Dual-profile decision: `docs/decisions/0011-dual-hardware-validation-profiles.md`

## Known limitations and risks

- The version markers identify Python contract families, not serialized wire compatibility.
- The Phase 1 Linux adapter still returns the smaller `HardwareProfile`; no conversion or migration boundary exists yet.
- `cgroup_limit_bytes=None` and `cgroup_quota_cores=None` mean no known bounded cgroup ceiling in this effective snapshot; Phase 2.6 structured degradation must distinguish probe failure before budget composition.
- Cross-object checks between a `HostInventory` and its linked `EffectiveResourceBudget` are not yet implemented; Phase 2.7 compatibility validation owns that gate.
- Normalized pressure requires adapters to retain raw provider evidence separately so normalization remains auditable.
- The full-workstation identity permits GPU placement but does not require a GPU budget, allowing degraded hosts; Phase 2.11 concrete profile validation must require the reference GPU for non-degraded benchmark claims.
- Concrete CPU, RAM, VRAM, and SSD reserve values remain undecided configuration data.
- The old and new resource contracts coexist until later composition work deliberately migrates callers.

## Operational notes

This change is immutable Python contracts, documentation, and in-memory tests only. It ran no hardware command, started no service, changed no cgroup, invoked no model, enabled no GPU, and modified no machine setting.

## Recommended next entry point

Begin Phase 2.3. Read this handoff, `docs/protocols/CORE_CONTRACTS.md`, the existing `experts/` and `verification/` public contracts, and the Application Fabric contract docs. Define separate versioned manifests for experts, verifiers, connectors, and memory records without importing Ollama, MCP, VS Code, one sandbox, or one storage engine. Preserve the distinction between installed package metadata and live runtime state.
