"""Versioned configuration for the optional installed peer listener."""

from __future__ import annotations

from dataclasses import dataclass

from fam_os.fabric.pairing import PeerEndpoint

PEER_SERVICE_CONFIGURATION_VERSION = "fam.fabric.peer-service-configuration/v1alpha1"


@dataclass(frozen=True, slots=True)
class PeerServiceConfiguration:
    enabled: bool
    display_name: str
    listen_host: str | None
    listen_port: int
    advertised_endpoint: PeerEndpoint | None
    contract_version: str = PEER_SERVICE_CONFIGURATION_VERSION

    def __post_init__(self) -> None:
        if not 1 <= len(self.display_name.strip()) <= 64:
            raise ValueError("peer service display name is invalid")
        if not 1 <= self.listen_port <= 65535:
            raise ValueError("peer service listen port is invalid")
        if self.enabled and (not self.listen_host or self.advertised_endpoint is None):
            raise ValueError("enabled peer service requires listen and advertised endpoints")
        if self.listen_host is not None and (
            not self.listen_host.strip()
            or any(character.isspace() or ord(character) < 33 for character in self.listen_host)
        ):
            raise ValueError("peer service listen host is invalid")
        if self.contract_version != PEER_SERVICE_CONFIGURATION_VERSION:
            raise ValueError("peer service configuration contract is unsupported")


def disabled_peer_configuration() -> PeerServiceConfiguration:
    return PeerServiceConfiguration(False, "FAM_OS device", None, 48121, None)
