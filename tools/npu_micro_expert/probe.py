#!/usr/bin/env python3
"""Compile and execute a deterministic routing micro-expert on OpenVINO NPU."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path

import numpy as np
import openvino as ov
import openvino.opset13 as ops


LABELS = ("code", "retrieval", "math", "general")
FEATURES = np.array([[1, 1, 0, 0, 0, 0, 0, 0]], dtype=np.float32)


def build_model() -> ov.Model:
    features = ops.parameter([1, 8], np.float32, name="features")
    weights = ops.constant(np.array([
        [4, 3, 0, 0, 0, 0, 0, 0],
        [0, 0, 4, 3, 0, 0, 0, 0],
        [0, 0, 0, 0, 4, 3, 0, 0],
        [0, 0, 0, 0, 0, 0, 2, 2],
    ], dtype=np.float32))
    bias = ops.constant(np.array([0, 0, 0, 0.25], dtype=np.float32))
    logits = ops.add(ops.matmul(features, weights, False, True), bias)
    return ov.Model([ops.softmax(logits, 1)], [features], "fam_route_linear_v1")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("/evidence"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    core = ov.Core()
    devices = tuple(core.available_devices)
    if "NPU" not in devices:
        raise RuntimeError(f"OpenVINO NPU unavailable; devices={devices}")
    model = build_model()
    xml_path = args.output / "routing-micro-expert.xml"
    bin_path = args.output / "routing-micro-expert.bin"
    ov.serialize(model, xml_path, bin_path)
    started = time.perf_counter_ns()
    compiled = core.compile_model(model, "NPU")
    compile_ms = _elapsed_ms(started)
    first_started = time.perf_counter_ns()
    output = np.asarray(compiled([FEATURES])[0])
    first_ms = _elapsed_ms(first_started)
    warm_ms = tuple(_infer_ms(compiled) for _ in range(5))
    observed = LABELS[int(np.argmax(output))]
    report = _raw_report(core, compiled, output, xml_path, bin_path, compile_ms, first_ms, warm_ms, observed)
    (args.output / "raw-probe.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, sort_keys=True))
    return 0


def _raw_report(core, compiled, output, xml_path, bin_path, compile_ms, first_ms, warm_ms, observed):
    return {
        "runtime_name": "OpenVINO",
        "runtime_version": ov.__version__,
        "user_mode_driver_version": _package_version("intel-level-zero-npu"),
        "level_zero_version": _package_version("libze1"),
        "available_devices": tuple(core.available_devices),
        "npu_full_device_name": core.get_property("NPU", "FULL_DEVICE_NAME"),
        "requested_device": "NPU",
        "execution_devices": _execution_devices(compiled),
        "cpu_fallback_allowed": False,
        "expert_id": "expert.route.intent-linear-npu",
        "capability_id": "route.intent.linear.v1",
        "model_format": "openvino-ir",
        "model_digest_sha256": _files_digest(xml_path, bin_path),
        "input_digest_sha256": hashlib.sha256(FEATURES.tobytes()).hexdigest(),
        "output_digest_sha256": hashlib.sha256(output.tobytes()).hexdigest(),
        "expected_label": "code",
        "observed_label": observed,
        "class_labels": LABELS,
        "output_probabilities": tuple(float(value) for value in output[0]),
        "compile_duration_ms": compile_ms,
        "first_inference_duration_ms": first_ms,
        "warm_inference_durations_ms": warm_ms,
        "fallback_used": False,
    }


def _infer_ms(compiled) -> float:
    started = time.perf_counter_ns()
    compiled([FEATURES])
    return _elapsed_ms(started)


def _elapsed_ms(started: int) -> float:
    return (time.perf_counter_ns() - started) / 1_000_000


def _files_digest(*paths: Path) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _package_version(name: str) -> str:
    result = subprocess.run(
        ("dpkg-query", "-W", "-f=${Version}", name),
        check=True, capture_output=True, text=True,
    )
    return result.stdout.strip()


def _execution_devices(compiled) -> tuple[str, ...]:
    value = compiled.get_property("EXECUTION_DEVICES")
    return (value,) if isinstance(value, str) else tuple(value)


if __name__ == "__main__":
    raise SystemExit(main())
