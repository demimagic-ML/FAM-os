"""Create a content-free remote route inside the normal Core inference record."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from fam_os.core.production.contracts import ModelIntent
from fam_os.fabric import (
    FabricRouteCandidate,
    LatencyAwareFabricScheduler,
    RemoteContextRequest,
    RemoteExecutionPlan,
    RemotePrivacyEvaluator,
    RemoteTaskDescriptor,
)
from fam_os.product.peer_capabilities import capability_for_intent


class ProductRemoteExecutionPlanner:
    def __init__(self, peer_management, *, clock=None, scheduler=None) -> None:
        self._peers = peer_management
        self._clock = clock or (lambda: datetime.now(UTC))
        self._scheduler = scheduler or LatencyAwareFabricScheduler()
        self._privacy = RemotePrivacyEvaluator()

    def plan(
        self, instance_id, request_id, intent, authority, *, verification_required,
    ) -> RemoteExecutionPlan:
        if intent is ModelIntent.MEDIA:
            raise PermissionError(
                "remote media requires an explicit binary-context contract",
            )
        peer = self._peers.peer(authority.enrollment_id)
        privacy = peer.privacy
        if privacy is None:
            raise PermissionError("remote execution defaults to zero disclosure")
        if privacy.revision != authority.expected_privacy_revision:
            raise RuntimeError("remote execution privacy revision changed")
        decision = self._privacy.decide(privacy.policy, RemoteContextRequest(
            self._peers.owner_id, peer.device_id, authority.purpose_id,
            authority.workspace_id, authority.sensitivity,
            authority.maximum_context_bytes, True,
        ))
        if not decision.allowed:
            raise PermissionError(
                "remote execution privacy denied: " + ",".join(decision.reason_codes),
            )
        if peer.latest_performance is None:
            raise PermissionError("remote execution requires an authenticated probe")
        capability_id = capability_for_intent(intent)
        declarations = tuple(
            item for item in peer.capabilities
            if capability_id in item.capability_ids
            and item.maximum_context_bytes >= authority.maximum_context_bytes
        )
        if not declarations:
            raise PermissionError("trusted peer has no eligible signed capability")
        candidates = tuple(FabricRouteCandidate(
            peer.device_id, item.expert_id, False, 0,
            peer.latest_performance.round_trip_milliseconds, True, True,
        ) for item in declarations)
        route = self._scheduler.decide(candidates)
        selected = next(
            item for item in declarations if item.expert_id == route.selected_expert_id
        )
        descriptor = RemoteTaskDescriptor(
            intent.value, (capability_id,),
            "verified" if verification_required else "unverified",
            authority.maximum_output_bytes,
        )
        return RemoteExecutionPlan(
            _plan_id(request_id, peer.device_id, selected.declaration_id),
            instance_id, request_id, authority.enrollment_id, peer.device_id,
            selected.expert_id, selected.model_ref, selected.expert_tier,
            selected.declaration_id,
            authority.expected_privacy_revision, authority.purpose_id,
            authority.workspace_id, authority.sensitivity, descriptor,
            authority.maximum_context_bytes, route.predicted_completion_milliseconds,
            (
                "authority.explicit_remote_confirmation",
                "privacy.exact_revision_and_scope",
                "capability.peer_root_signed",
                "scheduler.authenticated_network_measurement",
                "scheduler.cold_inference_unmeasured",
            ),
            self._clock(),
        )


def _plan_id(request_id: str, device_id: str, declaration_id: str) -> str:
    digest = hashlib.sha256(
        f"{request_id}|{device_id}|{declaration_id}".encode(),
    ).hexdigest()[:32]
    return "remote-plan-" + digest
