"""Authenticated local Application Fabric transport primitives."""

from fam_os.applications.transport.auth import (
    PeerAuthorizationPolicy, UnixPeerCredentials, unix_peer_credentials,
)
from fam_os.applications.transport.framing import (
    MAX_FRAME_BYTES, encode_frame, receive_frame, send_frame,
)
from fam_os.applications.transport.connection import AuthenticatedLocalConnection
from fam_os.applications.transport.broker import ConnectorRequestBroker
from fam_os.applications.transport.codec import contract_message, decode_contract_message
from fam_os.applications.transport.dispatch import (
    ApplicationMessageConsumer, RegistryMessageDispatcher,
)
from fam_os.applications.transport.endpoint import (
    UnixApplicationServer, UnixEndpointConfiguration,
)
from fam_os.applications.transport.ports import LocalMessageDispatcher
from fam_os.applications.transport.session import LocalTransportSession
from fam_os.applications.transport.wire import (
    LOCAL_TRANSPORT_VERSION, REQUEST_RESPONSE_KINDS, LocalMessage, LocalMessageKind,
)

__all__ = [
    "LOCAL_TRANSPORT_VERSION", "MAX_FRAME_BYTES", "LocalMessage",
    "LocalMessageDispatcher", "LocalMessageKind", "LocalTransportSession",
    "AuthenticatedLocalConnection", "PeerAuthorizationPolicy",
    "ConnectorRequestBroker",
    "UnixPeerCredentials", "encode_frame", "receive_frame", "send_frame",
    "unix_peer_credentials", "UnixApplicationServer", "UnixEndpointConfiguration",
    "ApplicationMessageConsumer", "RegistryMessageDispatcher", "contract_message",
    "decode_contract_message",
    "REQUEST_RESPONSE_KINDS",
]
