"""Owner-visible directory projection containing active trusted peers only."""

from dataclasses import dataclass

from fam_os.fabric.pairing import PeerEndpoint
from fam_os.fabric.peer_state import (
    PeerCapabilityDeclaration,
    PeerPerformanceObservation,
    PeerPrivacyPolicyRecord,
)

TRUSTED_PEER_DIRECTORY_VERSION = "fam.fabric.trusted-peer-directory/v1alpha1"


@dataclass(frozen=True, slots=True)
class TrustedPeerDirectoryEntry:
    enrollment_id: str
    enrollment_revision: int
    device_id: str
    display_name: str
    endpoint: PeerEndpoint
    capabilities: tuple[PeerCapabilityDeclaration, ...]
    latest_performance: PeerPerformanceObservation | None
    privacy: PeerPrivacyPolicyRecord | None
    trusted: bool = True
    contract_version: str = TRUSTED_PEER_DIRECTORY_VERSION

    def __post_init__(self) -> None:
        if not all((self.enrollment_id.strip(), self.device_id.strip(), self.display_name.strip())):
            raise ValueError("trusted peer directory identity is invalid")
        if self.enrollment_revision < 1:
            raise ValueError("trusted peer enrollment revision is invalid")
        if any(item.device_id != self.device_id for item in self.capabilities):
            raise ValueError("trusted peer capabilities differ from directory identity")
        if self.latest_performance is not None:
            if self.latest_performance.peer_device_id != self.device_id:
                raise ValueError("trusted peer performance differs from directory identity")
        if self.privacy is not None and self.privacy.peer_device_id != self.device_id:
            raise ValueError("trusted peer privacy differs from directory identity")
        if not self.trusted or self.contract_version != TRUSTED_PEER_DIRECTORY_VERSION:
            raise ValueError("untrusted devices cannot enter the trusted directory")
