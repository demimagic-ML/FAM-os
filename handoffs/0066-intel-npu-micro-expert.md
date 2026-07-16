# Handoff 0066: Intel NPU-compatible routing micro-expert

**Date:** 2026-07-16  
**Plan step:** Phase 7.8  
**Status:** Complete  
**Previous handoff:** `0065-ssd-model-paging.md`

## Objective

Investigate the reference workstation's Intel NPU with a real, bounded
micro-expert execution. Distinguish physical discovery, userspace readiness, and
actual device execution; never accept CPU fallback or emulation as NPU evidence.

## Scope completed

- Discovered the physical Arrow Lake `8086:ad1d` processing accelerator,
  `/dev/accel/accel0`, and active `intel_vpu` kernel driver.
- Recorded Ubuntu 24.04, kernel 6.17, module version, device presence, and the
  difference between denied direct user access and delegated container access.
- Verified current Intel/OpenVINO platform requirements from primary sources.
- Built a checksum-pinned Ubuntu container with Intel Linux NPU stack 1.33.0,
  Level Zero 1.27.0, OpenVINO 2026.2.0, and pinned Python dependencies.
- Passed only the accelerator device and numeric device group; disabled network,
  made the container root filesystem read-only, and used a bounded temporary FS.
- Created a deterministic OpenVINO IR linear intent-routing micro-expert with
  code, retrieval, math, and general classes.
- Compiled explicitly for `NPU`, verified the compiled execution device is
  exactly `NPU`, and prohibited fallback.
- Captured model/input/output digests, probabilities, classification, compile
  latency, first inference, and five warm inference durations.
- Added a strict public report contract, generated schema, positive/negative
  contract tests, canonical evidence tests, protocol documentation, ADR 0065,
  the Master Plan update, and this handoff.

## Explicitly not completed

- No permanent OpenVINO, Level Zero, compiler, firmware, udev, or group change
  was installed on the host.
- The probe does not add production NPU capacity to admission or placement.
- The deterministic linear router proves execution plumbing, not trained routing
  accuracy, language understanding, safety quality, or Phase 9 benchmark fitness.
- No CPU, `AUTO`, heterogeneous, or emulated result is represented as NPU work.
- Phase 7.9 cache telemetry/policy replay and Phase 7.10 prefetch remain open.

## Architecture and decisions

ADR 0065 requires three independent gates: physical hardware, userspace runtime,
and NPU-only compiled execution. Supported evidence requires `NPU` discovery,
explicit target `NPU`, execution devices exactly `("NPU",)`, and
`fallback_used=false`. Unsupported reports retain one explicit blocking gate and
cannot carry micro-expert evidence.

The interactive user is not in the accelerator's `render` group, while Docker
authority already exists. The reference probe therefore delegates the single
device and its numeric group into an isolated container. This tests real hardware
without mutating host access policy. It is an investigation mechanism, not the
final production service boundary.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/scheduler/npu_contracts.py` | Hardware, runtime, execution, and report invariants. |
| `src/fam_os/scheduler/__init__.py` | Public scheduler exports. |
| `src/fam_os/schemas/catalog.py` | Public NPU report schema registration. |
| `schemas/v1alpha1/fam.scheduler.npu-investigation.schema.json` | Generated strict schema. |
| `tools/npu_micro_expert/Dockerfile` | Pinned isolated Intel/OpenVINO runtime. |
| `tools/npu_micro_expert/probe.py` | OpenVINO model construction and NPU-only inference. |
| `tools/npu_micro_expert/host_probe.py` | Read-only host identity/access probe. |
| `tools/run_npu_investigation.py` | Image build, device delegation, evidence composition. |
| `tests/unit/test_npu_contracts.py` | Fail-closed NPU contract tests. |
| `tests/integration/test_npu_investigation_evidence.py` | Canonical live evidence gates. |
| `tests/contract/schema_scheduler_fixtures.py` | Strict schema round-trip fixture. |
| `docs/protocols/INTEL_NPU_MICRO_EXPERTS.md` | Investigation protocol and reproduction. |
| `docs/decisions/0065-require-npu-only-execution-evidence.md` | NPU evidence decision. |
| `artifacts/scheduler/phase7.8/intel-npu-micro-expert-canonical/` | Raw, strict, model, and summary artifacts. |

## Public interfaces

- `NPU_INVESTIGATION_CONTRACT_VERSION`
- `NpuInvestigationOutcome`
- `NpuHardwareEvidence`, `NpuRuntimeEvidence`
- `NpuMicroExpertEvidence`, `NpuInvestigationReport`
- `fam.scheduler.npu-investigation/v1alpha1`
- `tools/run_npu_investigation.py`

## Live evidence

Canonical directory:

```text
artifacts/scheduler/phase7.8/intel-npu-micro-expert-canonical/
```

- Hardware: Intel Arrow Lake NPU `8086:ad1d`.
- Kernel: `intel_vpu`, kernel `6.17.0-35-generic`.
- Runtime: OpenVINO `2026.2.0-21903-52ddc073857-releases/2026/2`.
- User-mode driver: `1.33.0.20260529-26625960453~ubuntu24.04`.
- Level Zero: `1.27.0-1~24.04~ppa2`.
- OpenVINO device: `Intel(R) AI Boost`.
- Execution devices: only `NPU`; fallback false.
- Result: expected and observed label `code`, probability 0.9970703125.
- Compile: 51.70289 ms; first inference: 7.926011 ms.
- Warm inference: 0.581183, 0.761190, 0.510626, 0.722435, 0.515669 ms.
- Model digest: `28f68d042554f46ab2eabf20b2d91e0d43becc05fc9c6b7b268d473b9546e4b3`.
- Runtime image digest: `f6993c1fecb471ab7cd6bbb85a7506d4d96da608d6241f8e87e7a429f80ebd55`.

The temporary exploratory container and image were removed. The final pinned
`fam-os-npu-openvino:2026.2-v1.33` image remains for exact local reproduction.

## Validation

Both `/usr/bin/python3` and `/tmp/fam-os-mcp-venv/bin/python` passed 693 tests
with three expected environment-dependent skips. All 67 generated schemas and
compileall passed. The size audit checked 387 source/tool Python files with no
file above 300 lines and no function above 50 lines.

The focused NPU suite proves contract rejection of fallback, CPU execution, and
wrong classifications; strict schema round trips; physical identity; NPU-only
runtime evidence; repeated execution; model digest integrity; and privacy-safe
summary output.

Larry refreshed 1,112 files, 2,920 symbols, 19,726 graph nodes, and 63,692 edges
after the implementation. This handoff itself is the one expected map-stale file.

## Known limitations and risks

- Existing Docker authority is privileged and is not equivalent to a least-
  privilege production NPU service grant.
- OpenVINO/NPU software evolves quickly; pinned versions preserve this proof but
  future upgrades require a new evidence run and compatibility decision.
- The micro-expert's feature extraction and weights are deterministic fixtures,
  not learned from a representative routing corpus.
- The report captures latency, not NPU power telemetry or energy-per-inference.
- The container installs the firmware package internally because Intel ships the
  release as one set, but it cannot update the read-only host firmware path.

## Recommended next entry point

Begin Phase 7.9. Define cache telemetry snapshots and deterministic policy replay
contracts before adding runtime logic. Replay must consume immutable observations
and reproduce admission, eviction, and cache decisions byte-for-byte without
consulting current host state. Preserve the Phase 7.7 page-cache evidence and
Phase 7.8 NPU report as independent inputs rather than collapsing storage cache,
RAM residency, GPU residency, and NPU runtime availability into one scalar.
