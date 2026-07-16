# Handoff 0004: Typed Linux hardware discovery

**Date:** 2026-07-16  
**Plan step:** Phase 1.5  
**Status:** Complete  
**Previous handoff:** `0003-application-weaving-boundary.md`

## Objective

Move the proven parent hardware profiler behind a provider-neutral typed contract and a read-only Linux adapter without copying its dictionary, serialization, CLI, or scheduling coupling.

## Scope completed

- Added immutable typed contracts for OS, CPU, memory, root storage, GPU, runtime-version, and complete hardware profiles.
- Added the scheduler-owned `HardwareDiscovery` port.
- Added small Linux adapter modules for filesystem paths, procfs parsing, bounded shell-free commands, NVIDIA parsing, standard-library host facts, and profile composition.
- Preserved the parent profiler's semantic inventory: capture time, hostname, OS, CPU, memory, root storage, NVIDIA GPUs, `/dev/accel` NPU paths, and Ollama version.
- Converted NVIDIA memory to bytes and power limits to numeric watts at the adapter boundary.
- Added synthetic non-sensitive fixtures and 10 new focused unit tests.
- Added an opt-in read-only parity test against parent `rnf.profile.collect_profile`.
- Recorded the host-inventory versus effective-cgroup-budget distinction in ADR 0004.

## Explicitly not completed

- No JSON or external hardware-profile schema was added; that remains Phase 2.2.
- No profile artifact or hostname was persisted.
- No CLI command or FAM Shell display was added.
- No cgroup, pressure, systemd, service, or effective runtime-budget discovery was added; those remain Phase 1.7 and Phase 7.
- No Ollama inference behavior moved; runtime-version probing is read-only and Phase 1.6 is next.
- No GPU other than NVIDIA or NPU detail beyond Linux device paths is currently discovered.

## Architecture and decisions

ADR 0004 places `HardwareProfile` and `HardwareDiscovery` in the scheduler domain while keeping Linux and command-output details in `adapters/linux`.

The profile is immutable host inventory. Its physical memory total must never be treated as the amount available to an expert. Model admission will later use the smaller effective cgroup budget, live pressure, operating-system headroom, foreground workload, and user policy.

Linux discovery uses no shell and performs no writes. Missing procfs data, `nvidia-smi`, Ollama, GPU, or NPU devices degrade to unknown values or empty collections where the contract permits.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/scheduler/hardware.py` | Provider-neutral hardware profile contracts |
| `src/fam_os/scheduler/ports/hardware.py` | Read-only hardware discovery port |
| `src/fam_os/scheduler/__init__.py` | Public hardware-contract exports |
| `src/fam_os/adapters/linux/paths.py` | Replaceable Linux discovery paths |
| `src/fam_os/adapters/linux/command.py` | Bounded shell-free command runner |
| `src/fam_os/adapters/linux/procfs.py` | Memory and CPU parsing/readers |
| `src/fam_os/adapters/linux/nvidia.py` | NVIDIA query and typed CSV parsing |
| `src/fam_os/adapters/linux/host.py` | Injectable standard-library host facts |
| `src/fam_os/adapters/linux/discovery.py` | Hardware-profile composition |
| `tests/fixtures/linux/` | Synthetic procfs and NVIDIA fixtures |
| `tests/unit/test_hardware_contracts.py` | Domain validation tests |
| `tests/unit/test_linux_procfs.py` | Procfs parser tests |
| `tests/unit/test_linux_nvidia.py` | NVIDIA parser and degradation tests |
| `tests/unit/test_linux_hardware_discovery.py` | Complete fake-driven adapter test |
| `tests/hardware/linux_profile_parity.py` | Opt-in parent semantic parity test |
| `docs/decisions/0004-read-only-hardware-discovery.md` | Hardware boundary ADR |
| `README.md`, `MASTER_PLAN.md`, component READMEs | Current status, evidence, ownership, and next step |

## Public interfaces

- `OperatingSystemProfile`
- `CpuProfile`
- `MemoryProfile`
- `StorageProfile`
- `GpuProfile`
- `RuntimeVersion`
- `HardwareProfile`
- `HardwareProfile.runtime_version(runtime_id)`
- `HardwareDiscovery.collect()`
- `LinuxHardwareDiscovery`
- `LinuxPaths`

These are source-level Python contracts. Phase 2 will define external serialization and compatibility policy.

## Validation

```bash
cd <REPO_ROOT>/FAM_OS
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Result: 24 tests passed, 0 failures.

```bash
cd <REPO_ROOT>/FAM_OS
PYTHONPATH=src:.. python3 -m unittest tests.hardware.linux_profile_parity -v
```

Result: 1 read-only hardware parity test passed. Stable parent semantics matched for schema version, hostname, OS, CPU, physical-memory totals, swap total, root-storage total, GPU names, NPU paths, and Ollama detection.

```bash
cd <REPO_ROOT>
python3 -m unittest discover -s tests -v
```

Result: all 10 parent RNF tests passed.

```bash
cd <REPO_ROOT>/FAM_OS
python3 -m compileall -q src tests
```

Result: completed successfully with no syntax errors.

The codebase knowledge graph was refreshed in fast mode. It found all seven queried hardware contract, adapter, parser, and test symbols, and graph-augmented code search found no parent `rnf` import under `FAM_OS/src/`.

```bash
cd <REPO_ROOT>
npx -y larry-dev@latest setup
```

Result: 116 files indexed, 24 artifacts written, verification clean.

## Evidence and artifacts

The read-only live smoke collection returned this non-sensitive summary:

| Fact | Result |
|---|---:|
| OS / architecture | Linux / x86_64 |
| Logical CPUs | 24 |
| Physical host RAM | 67,017,834,496 bytes |
| Root storage total | 2,013,991,550,976 bytes |
| Root storage free at capture | 551,380,189,184 bytes |
| GPU | NVIDIA GeForce RTX 5080 |
| GPU memory | 17,094,934,528 bytes |
| NPU device count | 1 |
| Ollama detected | Yes |

No hardware-profile artifact was written because it would contain hostname and device identifiers.

## Known limitations and risks

- The profile reports host RAM, not effective cgroup memory.
- CPU parsing covers common x86 and ARM procfs labels but is not yet a complete architecture taxonomy.
- NVIDIA is the only detailed GPU probe.
- NPU discovery currently records paths without capabilities or memory.
- Only the root filesystem is inventoried.
- Optional probe failures currently degrade silently; structured diagnostic telemetry is future work.
- The source-level schema is intentionally narrow and may receive additive Phase 2 fields.

## Operational notes

All operations were read-only. No services were started, no packages or models were installed, no device permissions changed, and no profile containing machine identity was persisted.

## Recommended next entry point

Begin Phase 1.6. Read `src/fam_os/core/ports/inference.py` and inspect the indexed parent functions in `rnf/benchmark.py`, `rnf/expert_experiment.py`, and `rnf/orchestrator.py`. Implement one Ollama adapter over an injectable HTTP transport, add fake response and error tests first, preserve load/token telemetry, and keep route prompts, expert policy, reporting, and orchestration outside the adapter.
