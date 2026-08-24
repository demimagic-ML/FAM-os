"""Application Fabric transports for explicitly enabled Linux fallbacks."""

from __future__ import annotations

import hashlib
import json
from base64 import b64encode
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from threading import Lock
from uuid import uuid4

from fam_os.applications import (
    ActionProposal, ActionResult, ActionStatus, AccessibleObjectRef,
    ApplicationFailure, ApplicationFailureCategory, ApplicationRetryDisposition,
    ConditionEvidence, ConditionRequirement, ConfirmationPolicy,
    ObservationResult, ObservationStatus, RelativeScreenPoint, Reversibility,
    ScreenInputInstruction, ScreenInputKind,
)
class AccessibilityFallbackTransport:
    def __init__(self, registration, bridge, process_id: int, include_text: bool) -> None:
        self.registration = registration
        self._bridge = bridge
        self._process_id = process_id
        self._include_text = include_text
        self._prepared: dict[str, object] = {}
        self._lock = Lock()

    def observe(self, request):
        _require_resource(request.resource_uri, f"process:{self._process_id}")
        snapshot = self._bridge.observe(self._process_id, self._include_text)
        if snapshot.issue_code is not None:
            return _unavailable(request, snapshot.captured_at, snapshot.issue_code)
        payload = _json_value(snapshot)
        revision = "atspi-tree:" + _payload_digest(payload)
        return ObservationResult(
            request.request_id, ObservationStatus.OBSERVED, snapshot.captured_at,
            payload, request.resource_uri, revision,
        )

    def prepare_action(self, request):
        _require_resource(request.resource_uri, f"process:{self._process_id}")
        reference = _accessible_reference(request.parameters.get("reference"))
        action_name = _text(request.parameters, "action_name")
        native = self._bridge.prepare_action(request.request_id, reference, action_name)
        proposal = ActionProposal(
            f"accessibility-proposal-{uuid4()}", request,
            {"reference_id": reference.reference_id, "action_name": action_name},
            Reversibility.IRREVERSIBLE, ConfirmationPolicy.ALWAYS,
            (ConditionRequirement(
                "accessibility.action.poststate", "accessibility.action.poststate",
                "The accessibility tree must expose the independently observed poststate.",
            ),),
        )
        with self._lock:
            self._prepared[proposal.proposal_id] = native
        return proposal

    def execute_action(self, proposal, confirmation):
        with self._lock:
            native = self._prepared.pop(proposal.proposal_id, None)
        if native is None:
            raise RuntimeError("accessibility proposal is unavailable or already consumed")
        evidence = self._bridge.perform_action(native)
        passed = evidence.invoked and evidence.after_fingerprint is not None
        condition = ConditionEvidence(
            "accessibility.action.poststate", "accessibility.action.poststate",
            passed, evidence.after_fingerprint or "Accessibility poststate unavailable.",
        )
        output = _json_value(evidence)
        return _action_result(proposal, condition, output, passed)


class ScreenInputFallbackTransport:
    def __init__(self, registration, bridge, target) -> None:
        self.registration = registration
        self._bridge = bridge
        self._target = target
        self._prepared: dict[str, object] = {}
        self._lock = Lock()

    def observe(self, request):
        _require_resource(request.resource_uri, f"window:{self._target.window_id}")
        observation = self._bridge.observe(self._target)
        if observation.frame is None:
            return _unavailable(
                request, observation.captured_at,
                observation.issue_code or "screen.unavailable",
            )
        payload = _json_value(observation)
        return ObservationResult(
            request.request_id, ObservationStatus.OBSERVED,
            observation.captured_at, payload, request.resource_uri,
            observation.frame.scene_id,
        )

    def prepare_action(self, request):
        _require_resource(request.resource_uri, f"window:{self._target.window_id}")
        scene_id = _text(request.parameters, "expected_scene_id")
        instruction = _screen_instruction(request.parameters.get("instruction"))
        native = self._bridge.prepare_action(
            request.request_id, self._target, scene_id, instruction,
        )
        proposal = ActionProposal(
            f"screen-proposal-{uuid4()}", request,
            {"expected_scene_id": scene_id, "instruction": _instruction_document(instruction)},
            Reversibility.IRREVERSIBLE, ConfirmationPolicy.ALWAYS,
            (ConditionRequirement(
                "screen.input.postframe", "screen.input.postframe",
                "The exact target window must provide an independent post-action frame.",
            ),),
        )
        with self._lock:
            self._prepared[proposal.proposal_id] = native
        return proposal

    def execute_action(self, proposal, confirmation):
        with self._lock:
            native = self._prepared.pop(proposal.proposal_id, None)
        if native is None:
            raise RuntimeError("screen proposal is unavailable or already consumed")
        evidence = self._bridge.perform_action(native)
        passed = evidence.invoked and evidence.after_scene_id is not None
        condition = ConditionEvidence(
            "screen.input.postframe", "screen.input.postframe", passed,
            evidence.after_scene_id or evidence.issue_code or "Screen postframe unavailable.",
        )
        return _action_result(
            proposal, condition, _json_value(evidence), passed,
        )


def _action_result(proposal, evidence, output, passed):
    if passed:
        return ActionResult(
            proposal.proposal_id, ActionStatus.VERIFIED, _now(), (evidence,), output,
        )
    return ActionResult(
        proposal.proposal_id, ActionStatus.POSTCONDITION_FAILED, _now(),
        (evidence,), output, error=ApplicationFailure(
            ApplicationFailureCategory.POSTCONDITION_FAILED,
            "fallback.postcondition_failed", "Fallback postcondition did not pass.",
            ApplicationRetryDisposition.AFTER_STATE_CHANGE,
        ),
    )


def _unavailable(request, observed_at, code):
    return ObservationResult(
        request.request_id, ObservationStatus.UNAVAILABLE, observed_at,
        resource_uri=request.resource_uri, error=ApplicationFailure(
            ApplicationFailureCategory.UNAVAILABLE, code,
            "The configured fallback target is unavailable.",
            ApplicationRetryDisposition.AFTER_STATE_CHANGE,
        ),
    )


def _accessible_reference(value):
    if not isinstance(value, Mapping):
        raise ValueError("accessibility reference must be an object")
    path = value.get("child_path")
    if not isinstance(path, (list, tuple)) or any(not isinstance(item, int) for item in path):
        raise ValueError("accessibility child path is invalid")
    return AccessibleObjectRef(
        value.get("process_id"), tuple(path), value.get("fingerprint"),
    )


def _screen_instruction(value):
    if not isinstance(value, Mapping):
        raise ValueError("screen instruction must be an object")
    kind = ScreenInputKind(value.get("kind"))
    if kind is ScreenInputKind.POINTER_CLICK:
        point = value.get("point")
        if not isinstance(point, Mapping):
            raise ValueError("screen point must be an object")
        return ScreenInputInstruction(kind, RelativeScreenPoint(
            point.get("x_millionths"), point.get("y_millionths"),
        ))
    keys = value.get("keys")
    if not isinstance(keys, (list, tuple)):
        raise ValueError("screen keys must be an array")
    return ScreenInputInstruction(kind, keys=tuple(keys))


def _instruction_document(value):
    point = None if value.point is None else {
        "x_millionths": value.point.x_millionths,
        "y_millionths": value.point.y_millionths,
    }
    return {"kind": value.kind.value, "point": point, "keys": list(value.keys)}


def _require_resource(value, expected):
    if value != expected:
        raise PermissionError("fallback request resource does not match configured target")


def _text(value, name):
    item = value.get(name)
    if not isinstance(item, str) or not item.strip():
        raise ValueError(f"fallback {name} must be text")
    return item


def _payload_digest(payload) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _json_value(value):
    if is_dataclass(value) and not isinstance(value, type):
        return {
            item.name: _json_value(getattr(value, item.name))
            for item in fields(value)
        }
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, bytes):
        return b64encode(value).decode("ascii")
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def _now():
    return datetime.now(timezone.utc)
