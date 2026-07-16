"""Real admission, routing, plan, and permission composition for acceptance."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fam_os.applications import PermissionGrant
from fam_os.core.admission import (
    InMemoryRequestAuthorityRegistry, InMemoryRequestReplayRegistry,
    RequestAdmissionService, RequestAuthorityGrant, RequestIdentity,
)
from fam_os.core.contracts import ExecutionPlan, TaskRequest
from fam_os.core.lifecycle import InMemoryPlanStateRepository, PlanLifecycleService
from fam_os.core.routing import CoreRoutingService
from fam_os.routing import RouteDecision, RouteName, RoutingResult


class DeclaredAcceptanceRouter:
    """Deterministic route for a predeclared acceptance scenario."""

    def __init__(self, route: RouteName):
        self.route_name = route

    def route(self, request):
        return RoutingResult(RouteDecision(
            self.route_name, 1.0, "Declared acceptance scenario.",
            request.required_capabilities,
        ))


class PermissionRegistry:
    def __init__(self, grants: tuple[PermissionGrant, ...]):
        self._grants = {item.grant_id: item for item in grants}

    def get(self, grant_id):
        return self._grants.get(grant_id)


@dataclass(slots=True)
class AcceptanceCoreSession:
    routed: object
    lifecycle: PlanLifecycleService
    permissions: PermissionRegistry
    plan_instance_id: str

    @classmethod
    def start(
        cls, request_id: str, prompt: str, plan_factory,
        application_grants: tuple[PermissionGrant, ...],
        route: RouteName = RouteName.CODE, verification_required=True,
    ):
        now = datetime.now(timezone.utc)
        capabilities = plan_factory(None).route.required_capabilities
        authority = RequestAuthorityGrant(
            f"authority-{request_id}", "local-user", f"shell-{request_id}",
            capabilities, now - timedelta(seconds=1), now + timedelta(minutes=30),
        )
        admission = RequestAdmissionService(
            InMemoryRequestAuthorityRegistry((authority,)),
            InMemoryRequestReplayRegistry(), clock=lambda: now,
            admission_id_factory=lambda: f"admission-{request_id}",
        ).admit(
            TaskRequest(request_id, prompt, capabilities, verification_required),
            RequestIdentity(authority.principal_id, authority.session_id, authority.authority_ref),
        )
        if not admission.accepted:
            raise RuntimeError("acceptance request admission failed")
        routed = CoreRoutingService(
            DeclaredAcceptanceRouter(route), clock=lambda: now,
        ).route(admission.admitted)
        if not routed.succeeded:
            raise RuntimeError("acceptance request routing failed")
        plan = plan_factory(routed.routed.routing.decision)
        lifecycle = PlanLifecycleService(
            InMemoryPlanStateRepository(),
            instance_id_factory=lambda: f"plan-instance-{request_id}",
        )
        started = lifecycle.start(routed.routed, plan)
        if started.rejection is not None:
            raise RuntimeError("acceptance plan start failed")
        return cls(
            routed.routed, lifecycle, PermissionRegistry(application_grants),
            started.snapshot.instance_id,
        )


def plan_factory(
    plan_id, request_id, capabilities, steps, transitions,
    verification_required=True,
):
    placeholder = RouteDecision(
        RouteName.CODE, 1.0, "Declared acceptance scenario.", capabilities,
    )

    def build(route):
        return ExecutionPlan(
            plan_id, request_id, route or placeholder, steps[0].step_id,
            steps, transitions, verification_required=verification_required,
        )

    return build
