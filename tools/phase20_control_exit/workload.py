"""Deterministic installed workload and health evidence for Phase 20.7."""

from __future__ import annotations


PRIMARY = "qwen2.5-coder:7b"
STRONG = "gemma4:26b"
OUTPUTS = tuple(f"PHASE20_CONTROL_RESULT_{index}" for index in range(1, 11))
PROMPTS = tuple(
    f"Write Python code for the resident-control workflow; reply exactly {output}"
    for output in OUTPUTS
)


def scripted_responses() -> tuple[dict, ...]:
    return (
        _response(PRIMARY, OUTPUTS[0]),
        _response(PRIMARY, "wrong-control-2-primary"),
        _response(PRIMARY, "wrong-control-2-repair"),
        _response(STRONG, OUTPUTS[1]),
        _response(PRIMARY, OUTPUTS[2]),
        _response(PRIMARY, "wrong-control-4-primary"),
        _response(PRIMARY, "wrong-control-4-repair"),
        _response(STRONG, OUTPUTS[3]),
        _response(PRIMARY, OUTPUTS[4]),
        _response(STRONG, OUTPUTS[5]),
        _response(PRIMARY, OUTPUTS[6]),
        _response(PRIMARY, OUTPUTS[7], 3.0),
        _response(PRIMARY, OUTPUTS[8], 3.0),
        _response(PRIMARY, OUTPUTS[9], 3.0),
    )


def scripted_health() -> tuple[dict, ...]:
    return (
        _healthy(65.0),
        _healthy(66.0),
        _healthy(66.0),
        _healthy(66.0),
        _healthy(67.0),
        _healthy(68.0),
        _healthy(69.0),
        _regressed(91.0),
        _regressed(92.0),
    )


def _response(model_ref: str, content: str, wall_seconds: float = 0.1) -> dict:
    return {
        "model_ref": model_ref,
        "content": content,
        "wall_seconds": wall_seconds,
    }


def _healthy(temperature: float) -> dict:
    return {
        "peak_temperature_c": temperature,
        "policy_conformant": True,
        "reason_codes": [
            "thermal.observed",
            "policy.runtime_bounds_satisfied",
        ],
    }


def _regressed(temperature: float) -> dict:
    return {
        "peak_temperature_c": temperature,
        "policy_conformant": False,
        "reason_codes": [
            "thermal.limit_exceeded",
            "policy.thermal_limit_violated",
        ],
    }
