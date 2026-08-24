"""Core-owned routing adapter for a classified production intent."""

from fam_os.core.production.intent import DeterministicIntentClassifier
from fam_os.routing import RouteDecision, RoutingResult


class PolicyIntentRouter:
    def __init__(self, intent) -> None:
        self._intent = intent

    def route(self, request):
        return RoutingResult(RouteDecision(
            DeterministicIntentClassifier.route(self._intent), 1.0,
            "Core policy classified the installed request.",
            request.required_capabilities,
        ))
