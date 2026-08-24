"""Persistence bridge from adapted inference to terminal health evidence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock

from fam_os.adaptation import (
    AdaptationInferenceObservation,
    AdaptationRuntimeHealth,
    LiveAdaptationSnapshot,
)
from fam_os.product.live_adaptation_drift import MAXIMUM_ADAPTATION_TEMPERATURE_C


@dataclass(frozen=True, slots=True)
class _ContextDecision:
    snapshot_id: str
    workflow_id: str
    context_tokens: int
    model_context_limit: int


class LiveAdaptationTelemetry:
    def __init__(self, repositories, health_sampler=None, now=None) -> None:
        self._repositories = repositories
        self._health = health_sampler or observe_adaptation_runtime_health
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._decisions: dict[str, _ContextDecision] = {}
        self._lock = RLock()

    def remember(
        self, request_id: str, snapshot: LiveAdaptationSnapshot | None,
        context_tokens: int, model_context_limit: int,
    ) -> None:
        with self._lock:
            if snapshot is None:
                self._decisions.pop(request_id, None)
                return
            self._decisions[request_id] = _ContextDecision(
                snapshot.snapshot_id, snapshot.workflow_id,
                context_tokens, model_context_limit,
            )

    def inference_completed(
        self, observation_id: str, request_id: str, model_ref: str, metrics,
    ) -> None:
        with self._lock:
            decision = self._decisions.pop(request_id, None)
        if decision is None:
            return
        health = self._health()
        observation = AdaptationInferenceObservation(
            observation_id, request_id, decision.snapshot_id, decision.workflow_id,
            model_ref, self._now(), metrics.wall_seconds, metrics.load_seconds,
            metrics.prompt_tokens, metrics.output_tokens, decision.context_tokens,
            decision.model_context_limit, health,
        )
        self._repositories.adaptation_controls.add_inference(observation)

    def clear(self) -> None:
        with self._lock:
            self._decisions.clear()


def observe_adaptation_runtime_health() -> AdaptationRuntimeHealth:
    temperatures = _thermal_zone_temperatures(Path("/sys/class/thermal"))
    if not temperatures:
        return AdaptationRuntimeHealth(
            None, True, ("thermal.observation_unavailable", "policy.runtime_bounds_satisfied"),
        )
    maximum = max(temperatures)
    if maximum > MAXIMUM_ADAPTATION_TEMPERATURE_C:
        return AdaptationRuntimeHealth(
            maximum, False, ("thermal.limit_exceeded", "policy.thermal_limit_violated"),
        )
    return AdaptationRuntimeHealth(
        maximum, True, ("thermal.observed", "policy.runtime_bounds_satisfied"),
    )


def _thermal_zone_temperatures(root: Path) -> tuple[float, ...]:
    values: list[float] = []
    try:
        paths = tuple(root.glob("thermal_zone*/temp"))
    except OSError:
        return ()
    for path in paths:
        try:
            raw = path.read_text("ascii").strip()
            value = float(raw)
        except (OSError, UnicodeError, ValueError):
            continue
        celsius = value / 1000 if abs(value) > 200 else value
        if -20 <= celsius <= 150:
            values.append(celsius)
    return tuple(values)
