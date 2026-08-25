"""Measured model routing for the local engineering agent."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


SCORECARD_VERSION = "fam.agent-harness-eval/v1"


@dataclass(frozen=True, slots=True)
class AgentModelEvaluation:
    model_ref: str
    passed_cases: int
    total_cases: int
    median_seconds: float
    evaluated_at: str

    def __post_init__(self) -> None:
        if (
            not self.model_ref.strip() or self.total_cases < 1
            or not 0 <= self.passed_cases <= self.total_cases
            or self.median_seconds < 0 or not self.evaluated_at.strip()
        ):
            raise ValueError("agent model evaluation is invalid")

    @property
    def completion_rate(self) -> float:
        return self.passed_cases / self.total_cases


def load_scorecard(path: Path) -> tuple[AgentModelEvaluation, ...]:
    try:
        payload = json.loads(path.read_text("utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return ()
    if not isinstance(payload, dict) or payload.get("version") != SCORECARD_VERSION:
        return ()
    raw = payload.get("models")
    if not isinstance(raw, list):
        return ()
    values = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            values.append(AgentModelEvaluation(
                str(item["model_ref"]), int(item["passed_cases"]),
                int(item["total_cases"]), float(item["median_seconds"]),
                str(item["evaluated_at"]),
            ))
        except (KeyError, TypeError, ValueError):
            continue
    return tuple(values)


def select_measured_model(
    installed: tuple[str, ...], evaluations: tuple[AgentModelEvaluation, ...],
) -> str | None:
    available = {item.casefold(): item for item in installed}
    candidates = [
        item for item in evaluations
        if item.model_ref.casefold() in available and item.total_cases >= 8
    ]
    if not candidates:
        return None
    winner = max(
        candidates,
        key=lambda item: (
            item.completion_rate, item.passed_cases,
            -item.median_seconds, item.evaluated_at,
        ),
    )
    return available[winner.model_ref.casefold()]
