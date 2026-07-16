"""Versioned static connector package manifest contracts."""

from __future__ import annotations

from dataclasses import dataclass

from fam_os.applications.capabilities import CapabilityDescriptor
from fam_os.applications.policy import ApplicationAuthority
from fam_os.registry import PackageMetadata


CONNECTOR_MANIFEST_CONTRACT_VERSION = "fam.connector.manifest/v1alpha1"


@dataclass(frozen=True, slots=True)
class ConnectorManifest:
    package: PackageMetadata
    connector_id: str
    display_name: str
    application_ids: tuple[str, ...]
    capabilities: tuple[CapabilityDescriptor, ...]
    transport_protocol_ids: tuple[str, ...]
    requested_authorities: tuple[ApplicationAuthority, ...]
    sandbox_profile_id: str
    supports_dynamic_capabilities: bool = False
    contract_version: str = CONNECTOR_MANIFEST_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for field_name in ("connector_id", "display_name", "sandbox_profile_id"):
            if not getattr(self, field_name).strip():
                raise ValueError(f"{field_name} must not be empty")
        if self.contract_version != CONNECTOR_MANIFEST_CONTRACT_VERSION:
            raise ValueError("unsupported connector manifest contract_version")
        self._require_unique_text("application_ids", self.application_ids)
        self._require_unique_text("transport_protocol_ids", self.transport_protocol_ids)
        capability_ids = tuple(item.capability_id for item in self.capabilities)
        if not capability_ids or len(set(capability_ids)) != len(capability_ids):
            raise ValueError("connector capability IDs must be present and unique")
        if len(set(self.requested_authorities)) != len(self.requested_authorities):
            raise ValueError("requested authorities must be unique")
        required = {item.required_authority for item in self.capabilities}
        if not required <= set(self.requested_authorities):
            raise ValueError("requested authorities must cover declared capabilities")

    @staticmethod
    def _require_unique_text(name: str, values: tuple[str, ...]) -> None:
        if not values or any(not value.strip() for value in values):
            raise ValueError(f"{name} requires non-empty values")
        if len(set(values)) != len(values):
            raise ValueError(f"{name} values must be unique")
