"""Unix peer credential extraction and local authorization."""

import socket
import struct
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class UnixPeerCredentials:
    process_id: int
    user_id: int
    group_id: int

    def __post_init__(self) -> None:
        if min(self.process_id, self.user_id, self.group_id) < 0:
            raise ValueError("peer credentials cannot be negative")


@dataclass(frozen=True, slots=True)
class PeerAuthorizationPolicy:
    allowed_user_id: int
    allowed_group_ids: tuple[int, ...] = ()

    def authorize(self, credentials: UnixPeerCredentials) -> bool:
        if credentials.user_id != self.allowed_user_id:
            return False
        return not self.allowed_group_ids or credentials.group_id in self.allowed_group_ids


def unix_peer_credentials(stream) -> UnixPeerCredentials:
    if not hasattr(socket, "SO_PEERCRED"):
        raise RuntimeError("Unix peer credentials are unavailable")
    size = struct.calcsize("3i")
    raw = stream.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, size)
    process_id, user_id, group_id = struct.unpack("3i", raw)
    return UnixPeerCredentials(process_id, user_id, group_id)
