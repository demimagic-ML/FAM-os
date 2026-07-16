"""Connector registration and provider-neutral local transport ports."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from fam_os.applications.actions import (
    ActionConfirmation,
    ActionPreparationRequest,
    ActionProposal,
    ActionResult,
)
from fam_os.applications.capabilities import CapabilityRegistryEntry
from fam_os.applications.identifiers import require_identifier, require_text
from fam_os.applications.identity import ApplicationInstance
from fam_os.applications.observations import ObservationRequest, ObservationResult
from fam_os.applications.payloads import JsonObject, freeze_payload
from fam_os.applications.timestamps import require_aware_datetime


APPLICATION_CONTRACT_VERSION = "fam.applications/v1alpha1"


class ConnectorTransportKind(StrEnum):
    NATIVE_LOCAL = "native_local"
    MCP_LOCAL = "mcp_local"
    OS_TOOL = "os_tool"
    ACCESSIBILITY = "accessibility"
    SCREEN_INPUT = "screen_input"


@dataclass(frozen=True, slots=True)
class ConnectorRegistration:
    connector_id: str
    transport_kind: ConnectorTransportKind
    protocol_id: str
    protocol_version: str
    instance: ApplicationInstance
    capabilities: tuple[CapabilityRegistryEntry, ...]
    connected_at: datetime
    contract_version: str = APPLICATION_CONTRACT_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "connector_id", require_identifier(self.connector_id, "connector_id")
        )
        for field_name in ("protocol_id", "protocol_version", "contract_version"):
            object.__setattr__(self, field_name, require_text(getattr(self, field_name), field_name))
        require_aware_datetime(self.connected_at, "connected_at")
        if self.connector_id != self.instance.connector_id:
            raise ValueError("registration connector must match application instance")
        if not self.capabilities:
            raise ValueError("connector registration requires capabilities")
        entry_ids = tuple(entry.entry_id for entry in self.capabilities)
        capability_ids = tuple(entry.capability_id for entry in self.capabilities)
        if len(set(entry_ids)) != len(entry_ids):
            raise ValueError("registered entry IDs must be unique")
        if len(set(capability_ids)) != len(capability_ids):
            raise ValueError("registered capability IDs must be unique per instance")
        for entry in self.capabilities:
            self._validate_entry(entry)

    def _validate_entry(self, entry: CapabilityRegistryEntry) -> None:
        if entry.connector_id != self.connector_id:
            raise ValueError("capability connector must match registration")
        if entry.instance_id != self.instance.instance_id:
            raise ValueError("capability instance must match registration")
        if entry.application_id != self.instance.application.application_id:
            raise ValueError("capability application must match registration")


class ConnectorEventKind(StrEnum):
    CAPABILITIES_CHANGED = "capabilities_changed"
    INSTANCE_CHANGED = "instance_changed"
    INSTANCE_CLOSED = "instance_closed"


@dataclass(frozen=True, slots=True)
class ConnectorEvent:
    event_id: str
    connector_id: str
    kind: ConnectorEventKind
    occurred_at: datetime
    payload: JsonObject = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("event_id", "connector_id"):
            object.__setattr__(
                self, field_name, require_identifier(getattr(self, field_name), field_name)
            )
        require_aware_datetime(self.occurred_at, "occurred_at")
        object.__setattr__(self, "payload", freeze_payload(self.payload))


class ConnectorTransport(Protocol):
    """Transport-neutral session implemented by native and MCP adapters."""

    def registration(self) -> ConnectorRegistration: ...

    def observe(self, request: ObservationRequest) -> ObservationResult: ...

    def prepare_action(self, request: ActionPreparationRequest) -> ActionProposal: ...

    def execute_action(
        self, proposal: ActionProposal, confirmation: ActionConfirmation
    ) -> ActionResult: ...

    def close(self) -> None: ...


class CapabilityRegistry(Protocol):
    """Core-facing registry port; storage and discovery remain replaceable."""

    def register(self, registration: ConnectorRegistration) -> None: ...

    def unregister(self, connector_id: str) -> None: ...

    def entries(self, instance_id: str | None = None) -> tuple[CapabilityRegistryEntry, ...]: ...
