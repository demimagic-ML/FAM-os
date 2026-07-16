"""Typed readers for the frozen RNF JSON fixtures used only by parity tools."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class RoutingFixture:
    base_url: str
    models: tuple[str, ...]
    tasks_file: Path
    context_tokens: int
    temperature: float
    seed: int | None
    timeout_seconds: float
    keep_alive: str


@dataclass(frozen=True, slots=True)
class ActivationFixture:
    policy_name: str
    base_url: str
    kernel_model: str
    expert_model: str
    evict_kernel: bool
    context_tokens: int
    max_output_tokens: int
    timeout_seconds: float
    keep_alive: str
    prompt: str


@dataclass(frozen=True, slots=True)
class VerifiedFixture:
    base_url: str
    kernel_model: str
    economical_model: str
    escalation_model: str
    context_tokens: int
    max_output_tokens: int
    repair_attempts: int
    escalation_repair_attempts: int
    escalate_on_failure: bool
    evict_before_escalation: bool
    timeout_seconds: float
    keep_alive: str
    repair_guidance: str
    repair_examples: tuple[str, ...]
    prompt: str


def load_routing_fixture(path: Path) -> RoutingFixture:
    payload = _payload(path)
    models = tuple(_text(item, "models") for item in _list(payload, "models"))
    if not models:
        raise ValueError("models must not be empty")
    return RoutingFixture(
        base_url=_text(payload.get("ollama_url"), "ollama_url"),
        models=models,
        tasks_file=path.parent.parent / _text(payload.get("tasks_file"), "tasks_file"),
        context_tokens=_positive_int(payload, "context_length"),
        temperature=_nonnegative_float(payload, "temperature"),
        seed=_optional_int(payload.get("seed"), "seed"),
        timeout_seconds=_positive_float(payload, "timeout_seconds"),
        keep_alive=_text(payload.get("keep_alive"), "keep_alive"),
    )


def load_activation_fixture(path: Path) -> ActivationFixture:
    payload = _payload(path)
    return ActivationFixture(
        policy_name=_text(payload.get("policy", path.stem), "policy"),
        base_url=_text(payload.get("ollama_url"), "ollama_url"),
        kernel_model=_text(payload.get("kernel_model"), "kernel_model"),
        expert_model=_text(payload.get("expert_model"), "expert_model"),
        evict_kernel=_boolean(payload.get("evict_kernel_before_expert", False)),
        context_tokens=_positive_int(payload, "context_length"),
        max_output_tokens=_positive_int(payload, "expert_num_predict", 256),
        timeout_seconds=_positive_float(payload, "timeout_seconds"),
        keep_alive=_text(payload.get("keep_alive"), "keep_alive"),
        prompt=_text(payload.get("prompt"), "prompt"),
    )


def load_verified_fixture(path: Path) -> VerifiedFixture:
    payload = _payload(path)
    return VerifiedFixture(
        base_url=_text(payload.get("ollama_url"), "ollama_url"),
        kernel_model=_text(payload.get("kernel_model"), "kernel_model"),
        economical_model=_text(payload.get("economical_expert"), "economical_expert"),
        escalation_model=_text(payload.get("escalation_expert"), "escalation_expert"),
        context_tokens=_positive_int(payload, "context_length"),
        max_output_tokens=_positive_int(payload, "expert_num_predict"),
        repair_attempts=_nonnegative_int(payload, "repair_attempts", 1),
        escalation_repair_attempts=_nonnegative_int(
            payload, "escalation_repair_attempts", 1
        ),
        escalate_on_failure=_boolean(payload.get("escalate_on_failure", True)),
        evict_before_escalation=_boolean(payload.get("evict_before_escalation", True)),
        timeout_seconds=_positive_float(payload, "timeout_seconds"),
        keep_alive=_text(payload.get("keep_alive"), "keep_alive"),
        repair_guidance=str(payload.get("repair_guidance", "")),
        repair_examples=tuple(
            _text(item, "repair_examples")
            for item in _optional_list(payload, "repair_examples")
        ),
        prompt=_text(payload.get("prompt"), "prompt"),
    )


def _payload(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("historical fixture must be a JSON object")
    return payload


def _list(payload: dict[str, Any], name: str) -> list[Any]:
    value = payload.get(name)
    if not isinstance(value, list):
        raise ValueError(f"{name} must be a list")
    return value


def _optional_list(payload: dict[str, Any], name: str) -> list[Any]:
    value = payload.get(name, [])
    if not isinstance(value, list):
        raise ValueError(f"{name} must be a list")
    return value


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _positive_int(payload: dict[str, Any], name: str, default: int | None = None) -> int:
    value = payload.get(name, default)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _nonnegative_int(payload: dict[str, Any], name: str, default: int) -> int:
    value = payload.get(name, default)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def _positive_float(payload: dict[str, Any], name: str) -> float:
    value = payload.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise ValueError(f"{name} must be positive")
    return float(value)


def _nonnegative_float(payload: dict[str, Any], name: str) -> float:
    value = payload.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise ValueError(f"{name} cannot be negative")
    return float(value)


def _optional_int(value: object, name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer or null")
    return value


def _boolean(value: object) -> bool:
    if not isinstance(value, bool):
        raise ValueError("boolean fixture value is invalid")
    return value
