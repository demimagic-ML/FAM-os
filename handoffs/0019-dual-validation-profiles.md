# Handoff 0019: Versioned dual validation profiles

**Date:** 2026-07-16  
**Plan step:** Phase 2.11  
**Status:** Complete  
**Previous handoff:** `0018-configuration-layering.md`

## Objective

Create strict, checked configuration documents for the required 16 GiB CPU compatibility baseline and full reference workstation while keeping reusable desired policy separate from current or privacy-sensitive machine discovery.

## Scope completed

- Added the `fam.validation-profile/v1alpha1` contract family.
- Added provider-neutral service memory, swap, CPU quota, and accelerator-visibility vocabulary.
- Added CPU-compatibility and full-host workload modes.
- Added `ValidationProfileDocument`, joining one scheduler configuration to one service resource envelope.
- Required `compat-cpu-16gb` to use CPU mode, exactly 16 GiB service memory, zero service/scheduler swap, denied accelerator visibility, disabled accelerator placement, and a bounded scheduler limit plus headroom.
- Required `full-reference-workstation` to use full-host mode, discovered accelerator visibility, enabled accelerator placement, and no 16 GiB-or-smaller profile service ceiling.
- Added `configs/profiles/compat-cpu-16gb.json` with a 16 GiB service ceiling, 14 GiB scheduler ceiling, 2 GiB headroom, zero swap, denied accelerator visibility, and bounded SSD cache.
- Added `configs/profiles/full-reference-workstation.json` with no artificial CPU/RAM cap, 2 reserved logical CPUs, 12 GiB RAM headroom, zero swap, discovered accelerators, bounded VRAM scheduling/reserve, and bounded NVMe cache/reserve.
- Kept device IDs, paths, CPU/GPU names, live capacity, current availability, model names, provider names, and software versions out of reusable profile data.
- Registered and generated the strict validation-profile document schema, raising the catalog from 34 to 35 roots.
- Decoded both checked JSON files through the strict schema boundary and compared their structure with the canonical encoder.
- Composed both profiles against the same deterministic discovered-workstation fixture.
- Proved the compatibility composition retains a physically visible GPU with zero placement authority.
- Proved the full composition exceeds the old 8-core/16-GiB constraints and exposes positive RAM, VRAM, and NVMe budgets.
- Added negative decoder tests for changed compatibility/full service ceilings.
- Added protocol documentation, ADR 0020, ownership documentation, and Master Plan updates.

## Explicitly not completed

- No systemd/cgroup/GPU-visibility adapter consumes `ServiceResourceEnvelope` yet; that is Phase 2.12 composition work.
- No benchmark orchestration was migrated and no workload was run.
- No live machine state or privacy-reviewed discovery artifact was captured; that is Phase 2.13.
- No model was loaded on CPU or GPU.
- No cgroup, swap, CPU affinity, environment variable, I/O controller, or GPU device visibility was changed.
- No performance, quality, power, thermal, or foreground responsiveness claim was produced.

## Architecture and decisions

ADR 0020 separates service authority from scheduler allocation. The compatibility service has a 16 GiB enforcement ceiling, but only 14 GiB is schedulable because 2 GiB remains explicit headroom. Representing both as one number would erase the reserve or mislabel the service ceiling.

The full profile's absent memory and CPU maximum means no profile-level artificial cap. It does not mean unbounded execution: live host/cgroup discovery and the 12 GiB RAM reserve still clamp the composed budget.

Reusable profiles contain stable policy only. Time-varying facts and potentially private identifiers belong to `DiscoveredResourceState`. Tests use a deterministic fixture and make no claim that it is a current workstation capture.

The service envelope is provider-neutral. It does not contain systemd properties, cgroup paths, CUDA variables, Ollama options, GPU indices, commands, or mount paths. Phase 2.12 must translate it behind existing adapter ports.

The new implementation module is `configuration/profiles.py` at 103 lines. All implementation modules remain below 300 lines and all functions remain below 50 lines.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/scheduler/configuration/profiles.py` | Versioned service envelope and concrete profile invariants |
| `src/fam_os/scheduler/configuration/__init__.py` | Public validation-profile exports |
| `src/fam_os/scheduler/__init__.py` | Scheduler-level profile exports |
| `src/fam_os/schemas/catalog.py` | Strict validation-profile document registration |
| `schemas/v1alpha1/fam.configuration.validation-profile-document.schema.json` | Generated cross-language schema |
| `configs/profiles/compat-cpu-16gb.json` | Checked minimum CPU-only policy |
| `configs/profiles/full-reference-workstation.json` | Checked full-host policy |
| `configs/profiles/README.md` | Profile values and policy/discovery boundary |
| `tests/contract/schema_configuration_fixtures.py` | Representative validation-profile root |
| `tests/contract/test_validation_profiles.py` | File decoding, invariants, privacy, and composition tests |
| `tests/contract/test_schema_roundtrip.py` | Catalog completeness extended to 35 roots |
| `docs/protocols/VALIDATION_PROFILE_DOCUMENTS.md` | Concrete values, service/scheduler distinction, and boundaries |
| `docs/protocols/CONFIGURATION_LAYERING.md` | Concrete profile implementation link |
| `docs/protocols/SERIALIZED_SCHEMA_COMPATIBILITY.md` | Current schema count and ADR coverage |
| `docs/architecture/HARDWARE_VALIDATION_PROFILES.md` | Phase 2.11 implementation status |
| `docs/decisions/0020-versioned-dual-validation-profile-documents.md` | Reusable policy versus captured state decision |
| `src/fam_os/scheduler/configuration/README.md` | Service-envelope ownership |
| `README.md` | Current implementation and next-step status |
| `MASTER_PLAN.md` | Phase 2.11 completion and Phase 2.12 entry point |
| `handoffs/README.md` | Handoff sequence entry |
| `handoffs/0019-dual-validation-profiles.md` | This implementation record |

## Public interfaces

- `VALIDATION_PROFILE_DOCUMENT_CONTRACT_VERSION`
- `AcceleratorVisibility`
- `ValidationWorkloadMode`
- `ServiceResourceEnvelope`
- `ValidationProfileDocument`

## Validation

```bash
cd <REPO_ROOT>/FAM_OS
PYTHONPATH=src:. python3 -m unittest \
  tests.contract.test_validation_profiles \
  tests.contract.test_schema_roundtrip
```

Result: all 13 focused tests passed in 0.123 seconds; 0 failures. Eight tests exercise the two checked files and five prove the complete 35-root schema catalog.

```bash
PYTHONPATH=src:. python3 -m unittest discover -s tests
```

Result: all 239 FAM_OS tests passed in 0.171 seconds; 0 failures. The previous suite contained 231 tests.

```bash
PYTHONPATH=src:. python3 tools/render_contract_schemas.py --check
```

Result: all 35 generated schema artifacts exactly match the catalog and domain annotations.

```bash
python3 -m compileall -q src tools tests
```

Result: completed successfully.

```bash
rg -n "Ollama|ollama|systemd|subprocess|vscode|WorkspaceEdit|MCP|mcp|RTX 5080|gpu-0|nvme-root" \
  src/fam_os/scheduler/configuration/profiles.py configs/profiles
```

Result: no provider, service manager, process, editor, connector protocol, captured GPU ID, captured storage ID, or hardware model dependency was found.

An AST audit found no implementation module at or above 300 lines and no function at or above 50 lines. The generated schema count is exactly 35.

## Evidence and artifacts

- `configs/profiles/compat-cpu-16gb.json`
- `configs/profiles/full-reference-workstation.json`
- `docs/protocols/VALIDATION_PROFILE_DOCUMENTS.md`
- `docs/decisions/0020-versioned-dual-validation-profile-documents.md`
- `tests/contract/test_validation_profiles.py`
- `schemas/v1alpha1/fam.configuration.validation-profile-document.schema.json`
- Dual-profile origin: ADR 0011
- Resource contracts: ADR 0015
- Layering authority: ADR 0019

## Known limitations and risks

- The service envelope is desired data until Phase 2.12 maps it to lifecycle and visibility adapters and verifies the applied state.
- The full profile's absent service memory cap must always be paired with fresh discovery/enforcement and explicit scheduler headroom; it must never be interpreted as permission to ignore cgroups.
- The compatibility composition test synthesizes a 16 GiB cgroup ceiling from the profile envelope. It is contract evidence, not a live cgroup measurement.
- The selected 2/12/1/100 GiB reserves and cache/VRAM ratios are initial policy values. Benchmark evidence may justify a new version, but current `v1alpha1` meaning must not be silently rewritten.
- CPU reservation remains topology-oblivious and generic accelerator/storage policy applies uniformly across devices.
- Zero service swap is explicit in both checked documents, but enforcement remains unproven until the benchmark service reports its cgroup values.
- The full profile does not name the RTX 5080 or 64 GiB RAM. This is intentional; Phase 2.13 pairs it with a privacy-reviewed current discovery artifact.
- No application weaving, UI, or expert-quality behavior is tested by these resource documents.

## Operational notes

This change added static configuration data, pure contracts, generated schemas, documentation, and in-memory tests. It performed no live probe, cgroup or GPU operation, service start, model inference, benchmark, or external application action.

## Recommended next entry point

Begin Phase 2.12. Inventory the existing parity entrypoints and the `ServiceLifecycle`/`ServiceSpec` boundary. Introduce one profile-driven benchmark service composition input that translates `ServiceResourceEnvelope` into provider-neutral lifecycle/resource/visibility intent. Preserve concrete systemd and Ollama settings in adapters. Both profiles must use the same workload orchestration; only decoded profile data and captured discovery may differ.
