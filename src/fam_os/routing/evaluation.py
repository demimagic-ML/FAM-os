"""Typed evaluation policy for the four-route kernel benchmark."""

from __future__ import annotations

import json
from dataclasses import dataclass
from statistics import fmean
from typing import Iterable

from fam_os.core.ports.inference import InferenceRuntime
from fam_os.routing.contracts import RouteName, RoutingRequest
from fam_os.routing.inference import ModelRouterSettings, build_model_routing_request
from fam_os.routing.parsing import RouteParseError, parse_route_evidence
from fam_os.telemetry.contracts import InferenceMetrics


@dataclass(frozen=True, slots=True)
class RoutingCase:
    case_id: str
    expected_route: RouteName
    prompt: str

    def __post_init__(self) -> None:
        if not self.case_id.strip() or not self.prompt.strip():
            raise ValueError("routing case ID and prompt must not be empty")


@dataclass(frozen=True, slots=True)
class RoutingCaseResult:
    case: RoutingCase
    predicted_route: RouteName | None
    structured: bool
    response: str
    metrics: InferenceMetrics

    @property
    def correct(self) -> bool:
        return self.predicted_route is self.case.expected_route


@dataclass(frozen=True, slots=True)
class RouteScore:
    route: RouteName
    correct: int
    total: int


@dataclass(frozen=True, slots=True)
class RoutingModelSummary:
    model_ref: str
    accuracy: float
    correct: int
    total: int
    structured_rate: float
    mean_wall_seconds: float
    mean_load_seconds: float
    mean_generation_tokens_per_second: float | None
    by_expected_route: tuple[RouteScore, ...]


def parse_routing_cases(lines: Iterable[str]) -> tuple[RoutingCase, ...]:
    cases: list[RoutingCase] = []
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        cases.append(_parse_case(line, line_number))
    if not cases:
        raise ValueError("evaluation contains no routing cases")
    if len({case.case_id for case in cases}) != len(cases):
        raise ValueError("routing case IDs must be unique")
    return tuple(cases)


def evaluate_routing_model(
    runtime: InferenceRuntime,
    settings: ModelRouterSettings,
    cases: tuple[RoutingCase, ...],
) -> tuple[RoutingCaseResult, ...]:
    return tuple(_evaluate_case(runtime, settings, case) for case in cases)


def summarize_routing_model(
    model_ref: str,
    results: tuple[RoutingCaseResult, ...],
) -> RoutingModelSummary:
    if not results:
        raise ValueError("routing results must not be empty")
    correct = sum(result.correct for result in results)
    rates = tuple(
        result.metrics.generation_tokens_per_second
        for result in results
        if result.metrics.generation_tokens_per_second is not None
    )
    return RoutingModelSummary(
        model_ref=model_ref,
        accuracy=correct / len(results),
        correct=correct,
        total=len(results),
        structured_rate=sum(result.structured for result in results) / len(results),
        mean_wall_seconds=fmean(result.metrics.wall_seconds for result in results),
        mean_load_seconds=fmean(result.metrics.load_seconds for result in results),
        mean_generation_tokens_per_second=fmean(rates) if rates else None,
        by_expected_route=_route_scores(results),
    )


def _parse_case(line: str, line_number: int) -> RoutingCase:
    try:
        payload = json.loads(line)
        return RoutingCase(
            case_id=str(payload["id"]),
            expected_route=RouteName(str(payload["expected_route"])),
            prompt=str(payload["prompt"]),
        )
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        raise ValueError(f"invalid routing case on line {line_number}") from error


def _evaluate_case(
    runtime: InferenceRuntime,
    settings: ModelRouterSettings,
    case: RoutingCase,
) -> RoutingCaseResult:
    request = RoutingRequest(case.case_id, case.prompt)
    response = runtime.chat(build_model_routing_request(settings, request))
    try:
        decision, structured = parse_route_evidence(response.content, request)
        predicted = decision.route
    except RouteParseError:
        predicted, structured = None, False
    return RoutingCaseResult(case, predicted, structured, response.content, response.metrics)


def _route_scores(results: tuple[RoutingCaseResult, ...]) -> tuple[RouteScore, ...]:
    scores: list[RouteScore] = []
    for route in RouteName:
        selected = tuple(result for result in results if result.case.expected_route is route)
        scores.append(RouteScore(route, sum(result.correct for result in selected), len(selected)))
    return tuple(scores)
