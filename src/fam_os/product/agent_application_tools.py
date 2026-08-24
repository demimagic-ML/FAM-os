"""Generic iterative-agent tools over the dynamic Application Fabric."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from fam_os.applications import (
    ActionConfirmation,
    ActionPreparationRequest,
    ConfirmationDecision,
    ObservationRequest,
)
from fam_os.core.agent import AgentToolDescriptor, AgentToolEffect, AgentToolRegistry


class ApplicationAgentTools:
    def __init__(self, provider_getter, owner_id: str) -> None:
        self._provider_getter = provider_getter
        self._owner_id = owner_id

    def register(self, registry: AgentToolRegistry) -> None:
        registry.register(_descriptor(
            "list_application_capabilities",
            "List live application, filesystem, OS-tool, MCP, browser fallback, and "
            "device-facing capabilities. Use this to discover integrations instead of "
            "guessing commands or capability names.",
            AgentToolEffect.OBSERVE, {},
        ), self.list_capabilities)
        registry.register(_descriptor(
            "observe_application",
            "Invoke one discovered observation capability with its instance ID, "
            "capability ID, optional parameters, and optional resource URI.",
            AgentToolEffect.OBSERVE,
            {
                "instance_id": {"type": "string"},
                "capability_id": {"type": "string"},
                "parameters": {"type": "object"},
                "resource_uri": {"type": "string"},
            }, required=("instance_id", "capability_id"),
        ), self.observe)
        registry.register(_descriptor(
            "act_on_application",
            "Prepare and execute one discovered application action through the live "
            "connector, returning its verified postcondition receipt. Available only "
            "under Full OS authority.",
            AgentToolEffect.OS_WRITE,
            {
                "instance_id": {"type": "string"},
                "capability_id": {"type": "string"},
                "summary": {"type": "string"},
                "parameters": {"type": "object"},
                "resource_uri": {"type": "string"},
                "expected_revision": {"type": "string"},
            }, required=("instance_id", "capability_id", "summary"),
        ), self.act)

    def list_capabilities(self, _arguments: dict[str, object]) -> str:
        entries = self._provider().entries()
        values = [{
            "instance_id": item.instance_id,
            "application_id": item.application_id,
            "capability_id": item.capability_id,
            "display_name": item.capability.display_name,
            "description": item.capability.description,
            "kind": item.capability.kind.value,
            "required_authority": item.capability.required_authority.value,
            "confirmation": item.capability.confirmation.value,
            "reversibility": item.capability.reversibility.value,
            "resource_scopes": list(item.resource_scopes),
        } for item in entries]
        return _encode({"capabilities": values, "count": len(values)})

    def observe(self, arguments: dict[str, object]) -> str:
        request = ObservationRequest(
            _identifier("observe"), _text(arguments, "instance_id"),
            _text(arguments, "capability_id"), _identifier("agent-grant"),
            _mapping(arguments.get("parameters")),
            _optional_text(arguments.get("resource_uri")),
        )
        return _encode(self._provider().observe(request))

    def act(self, arguments: dict[str, object]) -> str:
        request = ActionPreparationRequest(
            _identifier("action"), _text(arguments, "instance_id"),
            _text(arguments, "capability_id"), _identifier("agent-grant"),
            _text(arguments, "summary"), _mapping(arguments.get("parameters")),
            _optional_text(arguments.get("resource_uri")),
            _optional_text(arguments.get("expected_revision")),
        )
        provider = self._provider()
        proposal = provider.prepare_action(request)
        confirmation = ActionConfirmation(
            _identifier("confirmation"), proposal.proposal_id,
            request.permission_grant_id, ConfirmationDecision.APPROVED,
            self._owner_id, datetime.now(timezone.utc),
            "Approved by the active Full OS agent authority profile.",
        )
        return _encode(provider.execute_action(proposal, confirmation))

    def _provider(self):
        provider = self._provider_getter()
        if provider is None:
            raise LookupError("Application Fabric is unavailable")
        return provider


def _descriptor(tool_id, description, effect, properties, *, required=()):
    return AgentToolDescriptor(
        tool_id, description, effect,
        {"type": "object", "properties": properties, "required": list(required)},
    )


def _identifier(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def _text(arguments: dict[str, object], key: str) -> str:
    value = arguments.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be non-empty text")
    return value.strip()


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError("optional text argument must be non-empty when supplied")
    return value.strip()


def _mapping(value: object) -> dict[str, object]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError("parameters must be an object")
    return dict(value)


def _encode(value: object) -> str:
    return json.dumps(_jsonable(value), sort_keys=True, separators=(",", ":"))[:262_144]


def _jsonable(value: object):
    if is_dataclass(value) and not isinstance(value, type):
        return _jsonable(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    return value
