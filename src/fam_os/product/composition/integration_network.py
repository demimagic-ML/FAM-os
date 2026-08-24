"""Owner opt-in composition for the privileged integration network client."""

from dataclasses import dataclass
from pathlib import Path

from fam_os.adapters.crypto import Ed25519IntegrationNetworkAuthority
from fam_os.adapters.integration import UnixIntegrationNetworkBroker
from fam_os.fabric import PersistentDeviceIdentityStore


@dataclass(frozen=True, slots=True)
class ProductIntegrationNetworkClient:
    broker: UnixIntegrationNetworkBroker
    authority: Ed25519IntegrationNetworkAuthority
    signer_key_id: str


def compose_integration_network_client(
    socket_path: Path | None,
    *,
    identity_root: Path,
    display_name: str,
    owner_uid: int,
) -> ProductIntegrationNetworkClient | None:
    """Compose no network authority unless the owner selected a broker socket."""
    if socket_path is None:
        return None
    if not socket_path.is_absolute():
        raise ValueError("integration network broker socket must be absolute")
    credentials = PersistentDeviceIdentityStore(identity_root, owner_uid).resolve(
        display_name,
    )
    key_id = credentials.identity.device_id
    authority = Ed25519IntegrationNetworkAuthority(
        {}, signing_key_id=key_id, signing_key=credentials.identity_key,
    )
    return ProductIntegrationNetworkClient(
        UnixIntegrationNetworkBroker(socket_path), authority, key_id,
    )
