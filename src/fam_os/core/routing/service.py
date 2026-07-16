"""Permission-preserving Core routing lifecycle."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from fam_os.core.admission import AdmittedTaskRequest
from fam_os.core.contracts import (
    FailureCategory,
    FailureComponent,
    FailureEnvelope,
    RetryDisposition,
)
from fam_os.core.routing.contracts import CoreRoutingOutcome, RoutedTaskRequest
from fam_os.routing.contracts import RoutingRequest, RoutingResult
from fam_os.routing.ports import TaskRouter


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _identifier() -> str:
    return str(uuid4())


@dataclass(slots=True)
class CoreRoutingService:
    router: TaskRouter
    clock: Callable[[], datetime] = _utc_now
    error_id_factory: Callable[[], str] = _identifier

    def route(self, admitted: AdmittedTaskRequest) -> CoreRoutingOutcome:
        request_id = admitted.request.request_id
        if self.clock() >= admitted.permission.valid_until:
            return self._failure(
                request_id, FailureCategory.PERMISSION_DENIED,
                "routing.permission_expired",
                "Request permission expired before routing.",
                RetryDisposition.AFTER_USER_ACTION,
            )
        request = RoutingRequest(
            request_id, admitted.request.prompt,
            admitted.permission.authorized_capabilities,
        )
        try:
            result = self.router.route(request)
        except Exception:
            return self._failure(
                request_id, FailureCategory.UNAVAILABLE,
                "routing.provider_unavailable", "Routing is currently unavailable.",
                RetryDisposition.WITH_BACKOFF,
            )
        return self._validate(admitted, result)

    def _validate(self, admitted, result) -> CoreRoutingOutcome:
        request_id = admitted.request.request_id
        if not isinstance(result, RoutingResult):
            return self._invalid(request_id)
        try:
            routed = RoutedTaskRequest(admitted, result)
        except ValueError:
            return self._invalid(request_id)
        return CoreRoutingOutcome(request_id, routed=routed)

    def _invalid(self, request_id) -> CoreRoutingOutcome:
        return self._failure(
            request_id, FailureCategory.INCOMPATIBLE,
            "routing.invalid_result", "Routing returned incompatible evidence.",
            RetryDisposition.NEVER,
        )

    def _failure(self, request_id, category, code, message, retry):
        failure = FailureEnvelope(
            self.error_id_factory(), category, code, message,
            FailureComponent.ROUTING, retry,
        )
        return CoreRoutingOutcome(request_id, failure=failure)
