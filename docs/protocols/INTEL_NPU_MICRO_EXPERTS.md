# Intel NPU micro-expert investigation

## Purpose

Phase 7.8 determines whether the reference workstation can execute a bounded
FAM micro-expert on its physical Intel NPU. It does not treat device discovery,
CPU emulation, `AUTO` placement, or a successful model compile as inference
proof. A supported report requires the compiled model to identify exactly
`NPU` as its execution device and to record `fallback_used=false`.

The current reference workload is a tiny four-class linear intent router. Its
eight numeric features are deterministic and its labels are `code`, `retrieval`,
`math`, and `general`. This model is an execution and integration reference, not
a claim of production routing quality or a substitute for the benchmark-trained
micro-experts planned in Phase 9.

## Evidence gates

The `fam.scheduler.npu-investigation/v1alpha1` report separates three gates:

1. physical hardware: PCI vendor/device family, `intel_vpu`, kernel and device
   node;
2. userspace runtime: pinned Intel user-mode driver, Level Zero, OpenVINO,
   `NPU` discovery, and the full device name;
3. execution: OpenVINO IR digest, input/output digests, exact target and execution
   devices, classification result, compile time, first inference, and five warm
   inferences.

An unsupported host must carry one explicit `blocking_gate` and no fabricated
micro-expert evidence. A supported host must have all three gates and cannot
carry a blocking gate.

## Isolated runtime

The host has `/dev/accel/accel0`, but the interactive user does not directly
belong to its device group. The reproducible probe therefore uses the user's
existing Docker authority to pass only that device and its numeric group into a
network-disabled, read-only container. This does not modify host groups, udev,
firmware, system packages, or the kernel driver.

The container pins Ubuntu 24.04 by image digest, Intel Linux NPU user-mode stack
1.33.0 and Level Zero loader 1.27.0 by SHA-256, plus OpenVINO 2026.2.0 and its
Python dependency versions.

Intel's v1.33 release lists Arrow Lake, Ubuntu 24.04, kernel 6.17, Level Zero
1.27, and OpenVINO 2026.2 as a verified configuration. OpenVINO documents Linux
NPU support as requiring an NPU driver and kernel 6.6 or newer. See the
[Intel Linux NPU v1.33 release](https://github.com/intel/linux-npu-driver/releases/tag/v1.33.0),
[OpenVINO NPU configuration](https://docs.openvino.ai/nightly/get-started/install-openvino/configurations/configurations-intel-npu.html),
and [OpenVINO NPU device guide](https://docs.openvino.ai/2026/openvino-workflow/running-inference/inference-devices-and-modes/npu-device.html).

## Reproduction

```bash
PYTHONPATH=src:. python3 tools/run_npu_investigation.py \
  --output artifacts/scheduler/phase7.8/intel-npu-micro-expert-canonical
```

The runner builds the checksum-pinned image, delegates only the accelerator
device, disables networking, compiles explicitly for `NPU`, performs inference,
and writes the strict report, raw probe, serialized OpenVINO model, and summary.

## Canonical result

The Arrow Lake device `8086:ad1d` was driven by `intel_vpu` and surfaced by
OpenVINO as `Intel(R) AI Boost`. The compiled model reported only `NPU`, selected
the expected `code` label, and completed five warm inferences without fallback.
Exact timings and immutable digests live under
`artifacts/scheduler/phase7.8/intel-npu-micro-expert-canonical/`.

## Boundary

This investigation establishes technical feasibility and a strict evidence
shape. It does not yet add NPU capacity to admission policy, schedule production
requests, benchmark real language/safety routing quality, or install a permanent
host runtime. Those are later Expert Fabric and production-hardening concerns.
