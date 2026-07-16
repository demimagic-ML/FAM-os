"""Deterministic parsing for model-generated routing decisions."""

from __future__ import annotations

import json
import re
from typing import Any

from fam_os.routing.contracts import RouteDecision, RouteName, RoutingRequest


class RouteParseError(ValueError):
    """Raised when a router response contains no supported route."""


def parse_route_decision(content: str, request: RoutingRequest) -> RouteDecision:
    decision, _ = parse_route_evidence(content, request)
    return decision


def parse_route_evidence(
    content: str,
    request: RoutingRequest,
) -> tuple[RouteDecision, bool]:
    payload = _json_payload(content)
    if payload is not None:
        route = _route_name(payload.get("route"))
        if route is not None:
            decision = RouteDecision(
                route,
                _confidence(payload.get("confidence")),
                _reason(payload.get("reason"), route),
                request.required_capabilities,
            )
            return decision, True
    route = _route_from_text(content)
    if route is None:
        raise RouteParseError("router response contains no supported route")
    decision = RouteDecision(
        route=route,
        confidence=0.5,
        reason="route recovered from non-JSON router response",
        required_capabilities=request.required_capabilities,
    )
    return decision, False


def _json_payload(content: str) -> dict[str, Any] | None:
    candidates = [content.strip()]
    match = re.search(r"\{.*?\}", content, flags=re.DOTALL)
    if match:
        candidates.append(match.group(0))
    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(payload, dict):
            return payload
    return None


def _route_name(value: object) -> RouteName | None:
    try:
        return RouteName(str(value).strip().lower())
    except ValueError:
        return None


def _route_from_text(content: str) -> RouteName | None:
    lowered = content.lower()
    for route in RouteName:
        if re.search(rf"\b{route.value}\b", lowered):
            return route
    return None


def _confidence(value: object) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.5
    return min(1.0, max(0.0, confidence))


def _reason(value: object, route: RouteName) -> str:
    reason = str(value or "").strip()
    return reason or f"router selected {route.value}"
