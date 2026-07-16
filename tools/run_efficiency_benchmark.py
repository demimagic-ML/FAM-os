#!/usr/bin/env python3
"""Measure quality per byte, second, and sampled NVIDIA joule."""

import argparse
import json
import subprocess
import threading
import time
from dataclasses import asdict
from pathlib import Path

from fam_os.adapters.ollama import OllamaModelCatalog, OllamaRuntime, OllamaSettings
from fam_os.core.ports.inference import InferenceMessage, InferenceRequest, MessageRole
from fam_os.experts.efficiency_reports import (
    ExpertEfficiencyMeasurement, PowerSample, build_efficiency_report,
)

CASES = (("2+3", "5"), ("capital of France", "Paris"),
         ("opposite of cold", "hot"), ("7 times 6", "42"),
         ("first letter of alphabet", "A"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    args = parser.parse_args()
    settings = OllamaSettings(args.ollama_url, 180)
    measurements = tuple(_measure(model, settings) for model in (
        "qwen3:1.7b", "llama3.2:3b", "granite3.3:2b",
    ))
    report = build_efficiency_report(
        "phase9.7-workstation-v1", "nvidia-smi.power.draw",
        "fam.efficiency.simple-qa/v1", measurements,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(asdict(report), indent=2, sort_keys=True) + "\n")


def _measure(model_ref, settings):
    samples, stop = [], threading.Event()
    thread = threading.Thread(target=_sample_power, args=(samples, stop), daemon=True)
    started = time.perf_counter()
    thread.start()
    answers = _ask(model_ref, settings)
    stop.set()
    thread.join()
    wall = time.perf_counter() - started
    if len(samples) < 2:
        raise RuntimeError("NVIDIA meter produced fewer than two samples")
    energy = _joules(samples)
    artifact = OllamaModelCatalog(settings).observe(model_ref)
    correct = sum(_normalize(value) == _normalize(expected) for value, (_, expected) in zip(answers, CASES))
    return ExpertEfficiencyMeasurement(
        f"expert.efficiency.{model_ref.replace(':', '-')}", model_ref,
        artifact.digest.value, correct / len(CASES), artifact.size_bytes, wall,
        energy, tuple(PowerSample(offset, watts) for offset, watts in samples),
    )


def _ask(model_ref, settings):
    prompt = "Answer each item with only its short answer. Return JSON array: " + json.dumps([q for q, _ in CASES])
    request = InferenceRequest(
        model_ref, (InferenceMessage(MessageRole.USER, prompt),), 2048, 128,
        json_output=True, temperature=0,
    )
    raw = OllamaRuntime(settings).chat(request).content
    values = json.loads(raw)
    if isinstance(values, dict):
        original = values
        values = original.get("answers", original.get("answer"))
        if values is None and len(original) == 1:
            values = next(iter(original.values()))
        if values is None and len(original) == len(CASES):
            values = list(original.values())
    if not isinstance(values, list) or len(values) != len(CASES):
        raise ValueError(f"{model_ref} did not return one answer per case: {raw[:500]}")
    return tuple(str(value) for value in values)


def _sample_power(samples, stop):
    origin = time.perf_counter()
    while not stop.is_set() or len(samples) < 2:
        output = subprocess.run(
            ["nvidia-smi", "--query-gpu=power.draw", "--format=csv,noheader,nounits"],
            check=True, capture_output=True, text=True,
        ).stdout.splitlines()[0]
        samples.append((time.perf_counter() - origin, float(output)))
        stop.wait(0.1)


def _joules(samples):
    return sum((right[0] - left[0]) * (left[1] + right[1]) / 2 for left, right in zip(samples, samples[1:]))


def _normalize(value):
    return str(value).strip().casefold().rstrip(".")


if __name__ == "__main__":
    main()
