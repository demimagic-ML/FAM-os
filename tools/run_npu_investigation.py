#!/usr/bin/env python3
"""Build the pinned NPU runtime and capture a real NPU-only micro-expert run."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from fam_os.scheduler import (
    NpuInvestigationOutcome,
    NpuInvestigationReport,
    NpuMicroExpertEvidence,
    NpuRuntimeEvidence,
)
from fam_os.schemas import encode_document
from tools.npu_micro_expert.host_probe import collect_hardware_evidence, device_group_id


IMAGE = "fam-os-npu-openvino:2026.2-v1.33"
DEVICE = "/dev/accel/accel0"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--image", default=IMAGE)
    parser.add_argument("--skip-build", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc)
    hardware = collect_hardware_evidence()
    if not args.skip_build:
        _build(args.image)
    image_digest = _image_digest(args.image)
    _run(args.image, output)
    raw = json.loads((output / "raw-probe.json").read_text(encoding="utf-8"))
    runtime = _runtime(raw)
    micro_expert = _micro_expert(raw)
    report = NpuInvestigationReport(
        "npu-investigation-live-20260716", started, datetime.now(timezone.utc),
        "full-reference-workstation", NpuInvestigationOutcome.SUPPORTED,
        hardware, runtime, micro_expert, None,
    )
    _write_json(output / "npu-investigation-report.json", encode_document(report))
    summary = _summary(report, image_digest)
    _write_json(output / "summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def _build(image: str) -> None:
    root = Path(__file__).resolve().parent / "npu_micro_expert"
    subprocess.run(("docker", "build", "--pull", "-t", image, str(root)), check=True)


def _run(image: str, output: Path) -> None:
    command = (
        "docker", "run", "--rm", f"--device={DEVICE}",
        "--group-add", str(device_group_id()), "--user", f"{os.getuid()}:{os.getgid()}",
        "--network", "none", "--read-only", "--tmpfs", "/tmp:rw,noexec,nosuid,size=32m",
        "--env", "HOME=/tmp", "--env", "OPENVINO_TELEMETRY_DISABLED=1",
        "--mount", f"type=bind,src={output},dst=/evidence",
        image, "--output", "/evidence",
    )
    subprocess.run(command, check=True)


def _image_digest(image: str) -> str:
    result = subprocess.run(
        ("docker", "image", "inspect", "--format={{.Id}}", image),
        check=True, capture_output=True, text=True,
    )
    return result.stdout.strip().removeprefix("sha256:")


def _runtime(raw: dict[str, object]) -> NpuRuntimeEvidence:
    return NpuRuntimeEvidence(
        str(raw["runtime_name"]), str(raw["runtime_version"]),
        str(raw["user_mode_driver_version"]), str(raw["level_zero_version"]),
        tuple(raw["available_devices"]), str(raw["npu_full_device_name"]),
        str(raw["requested_device"]), tuple(raw["execution_devices"]),
        bool(raw["cpu_fallback_allowed"]), True,
    )


def _micro_expert(raw: dict[str, object]) -> NpuMicroExpertEvidence:
    return NpuMicroExpertEvidence(
        str(raw["expert_id"]), str(raw["capability_id"]), str(raw["model_format"]),
        str(raw["model_digest_sha256"]), str(raw["input_digest_sha256"]),
        str(raw["output_digest_sha256"]), str(raw["expected_label"]),
        str(raw["observed_label"]), tuple(raw["class_labels"]),
        tuple(raw["output_probabilities"]), float(raw["compile_duration_ms"]),
        float(raw["first_inference_duration_ms"]),
        tuple(raw["warm_inference_durations_ms"]), bool(raw["fallback_used"]),
    )


def _summary(report: NpuInvestigationReport, image_digest: str) -> dict[str, object]:
    expert = report.micro_expert
    assert expert is not None
    return {
        "schema_version": 1, "outcome": report.outcome.value,
        "hardware": report.hardware.device_family,
        "kernel_driver": report.hardware.kernel_driver,
        "host_user_direct_access": report.hardware.host_user_direct_access,
        "access_mechanism": report.hardware.access_mechanism,
        "runtime_version": report.runtime.runtime_version,
        "runtime_devices": report.runtime.available_devices,
        "execution_devices": report.runtime.execution_devices,
        "npu_full_device_name": report.runtime.npu_full_device_name,
        "fallback_used": expert.fallback_used,
        "observed_label": expert.observed_label,
        "compile_duration_ms": expert.compile_duration_ms,
        "first_inference_duration_ms": expert.first_inference_duration_ms,
        "warm_inference_durations_ms": expert.warm_inference_durations_ms,
        "runtime_image_digest_sha256": image_digest,
    }


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
