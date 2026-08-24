"""Provider-neutral deterministic network-enforcement contracts."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
import ipaddress
import re


NETWORK_ENFORCEMENT_VERSION = "fam.supervisor.network-enforcement/v1alpha1"
_IDENTITY = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,255}\Z")
_DNS = re.compile(r"[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?\Z")


class NetworkAttachmentKind(StrEnum):
    LINUX_NAMESPACE = "linux_namespace"
    DOCKER_INTERNAL_NETWORK = "docker_internal_network"


@dataclass(frozen=True, slots=True)
class NetworkEnforcementSpec:
    enforcement_id: str
    environment_id: str
    attachment_kinds: tuple[NetworkAttachmentKind, ...]
    destinations: tuple[str, ...]
    maximum_network_bytes: int
    expires_at: datetime
    request_digest: str
    contract_version: str = NETWORK_ENFORCEMENT_VERSION

    def __post_init__(self) -> None:
        if not self.enforcement_id.startswith("fam-network-"):
            raise ValueError("network enforcement ID is outside the FAM namespace")
        if any(not _IDENTITY.fullmatch(item) for item in (
            self.enforcement_id, self.environment_id,
        )):
            raise ValueError("network enforcement identity is invalid")
        if (
            not self.attachment_kinds
            or any(not isinstance(item, NetworkAttachmentKind) for item in self.attachment_kinds)
            or len(set(self.attachment_kinds)) != len(self.attachment_kinds)
        ):
            raise ValueError("network attachment kinds are invalid")
        if not self.destinations or len(set(self.destinations)) != len(self.destinations):
            raise ValueError("network destinations must be nonempty and unique")
        for destination in self.destinations:
            _endpoint(destination)
        if self.maximum_network_bytes <= 0:
            raise ValueError("network byte limit must be positive")
        if self.expires_at.tzinfo is None:
            raise ValueError("network expiry must be timezone-aware")
        if not re.fullmatch(r"[0-9a-f]{64}", self.request_digest):
            raise ValueError("network request digest is invalid")
        if self.contract_version != NETWORK_ENFORCEMENT_VERSION:
            raise ValueError("network enforcement version is unsupported")


@dataclass(frozen=True, slots=True)
class NetworkAttachment:
    kind: NetworkAttachmentKind
    attachment_reference: str
    proxy_uri: str

    def __post_init__(self) -> None:
        if not isinstance(self.kind, NetworkAttachmentKind):
            raise ValueError("network attachment kind is invalid")
        if not self.attachment_reference or "\0" in self.attachment_reference:
            raise ValueError("network attachment reference is invalid")
        if not self.proxy_uri.startswith("http://") or "@" in self.proxy_uri:
            raise ValueError("network proxy URI is invalid")


@dataclass(frozen=True, slots=True)
class NetworkEnforcementLease:
    enforcement_id: str
    attachments: tuple[NetworkAttachment, ...]
    destinations: tuple[str, ...]
    maximum_network_bytes: int
    issued_at: datetime
    expires_at: datetime
    evidence_digest: str

    def __post_init__(self) -> None:
        if not self.enforcement_id.startswith("fam-network-"):
            raise ValueError("network lease enforcement ID is invalid")
        if not self.attachments or len({item.kind for item in self.attachments}) != len(self.attachments):
            raise ValueError("network lease attachments are invalid")
        if not self.destinations or len(set(self.destinations)) != len(self.destinations):
            raise ValueError("network lease destinations are invalid")
        for destination in self.destinations:
            _endpoint(destination)
        if self.maximum_network_bytes <= 0:
            raise ValueError("network lease byte limit must be positive")
        if self.issued_at.tzinfo is None or self.expires_at.tzinfo is None:
            raise ValueError("network lease timestamps must be aware")
        if self.expires_at <= self.issued_at:
            raise ValueError("network lease expiry is invalid")
        _digest(self.evidence_digest)


@dataclass(frozen=True, slots=True)
class NetworkUsageSnapshot:
    enforcement_id: str
    destinations: tuple[str, ...]
    transmitted_bytes: int
    received_bytes: int
    maximum_network_bytes: int
    quota_exceeded: bool
    finalized: bool
    observed_at: datetime
    evidence_digest: str

    def __post_init__(self) -> None:
        if not self.enforcement_id.startswith("fam-network-"):
            raise ValueError("network usage enforcement ID is invalid")
        if len(set(self.destinations)) != len(self.destinations):
            raise ValueError("network usage destinations are duplicated")
        for destination in self.destinations:
            _endpoint(destination)
        values = self.transmitted_bytes, self.received_bytes
        if any(isinstance(item, bool) or item < 0 for item in values):
            raise ValueError("network usage byte counts are invalid")
        if self.maximum_network_bytes <= 0 or sum(values) > self.maximum_network_bytes:
            raise ValueError("network usage exceeds its byte limit")
        if self.quota_exceeded and not self.finalized:
            raise ValueError("network quota exhaustion must be finalized")
        if self.observed_at.tzinfo is None:
            raise ValueError("network usage timestamp must be aware")
        _digest(self.evidence_digest)


def split_network_endpoint(value: str) -> tuple[str, int]:
    if value.startswith("["):
        closing = value.find("]")
        if closing < 0 or value[closing + 1:closing + 2] != ":":
            raise ValueError("network destination requires canonical host and port")
        host, separator, port = value[1:closing], ":", value[closing + 2:]
        try:
            if ipaddress.ip_address(host).version != 6:
                raise ValueError
        except ValueError as error:
            raise ValueError("network destination host is invalid") from error
        address_valid = True
    else:
        host, separator, port = value.rpartition(":")
        address_valid = False
    if not separator or not host or not port.isdigit() or str(int(port)) != port:
        raise ValueError("network destination requires canonical host and port")
    if not 1 <= int(port) <= 65535:
        raise ValueError("network destination port is invalid")
    if not address_valid:
        try:
            ipaddress.ip_address(host)
        except ValueError:
            if host != host.lower() or not _DNS.fullmatch(host):
                raise ValueError("network destination host is invalid")
    return host, int(port)


def _endpoint(value: str) -> None:
    split_network_endpoint(value)


def _digest(value: str) -> None:
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("network evidence digest is invalid")
