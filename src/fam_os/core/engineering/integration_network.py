"""Trusted accounting evidence for allowlisted integration egress."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
import ipaddress
import re
import base64
import json

from fam_os.core.engineering._validation import aware, digest, positive, text, texts
from fam_os.core.engineering.version import ENGINEERING_CONTRACT_VERSION


_DNS_NAME = re.compile(
    r"(?=.{1,253}\Z)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)*"
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z"
)


def validate_integration_network_endpoint(value: str) -> None:
    """Require one canonical host-or-IP plus an explicit destination port."""

    text(value, "network endpoint")
    if value.startswith("["):
        closing = value.find("]")
        host, separator, port_text = value[1:closing], value[closing + 1:closing + 2], value[closing + 2:]
        if closing < 0 or separator != ":":
            raise ValueError("network endpoint must include an explicit port")
        try:
            if ipaddress.ip_address(host).version != 6:
                raise ValueError
        except ValueError as error:
            raise ValueError("network endpoint IPv6 address is invalid") from error
    else:
        host, separator, port_text = value.rpartition(":")
        if separator != ":" or not host:
            raise ValueError("network endpoint must include an explicit port")
        try:
            ipaddress.ip_address(host)
        except ValueError:
            if host != host.lower() or not _DNS_NAME.fullmatch(host):
                raise ValueError("network endpoint host is not canonical")
    try:
        port = int(port_text)
    except ValueError as error:
        raise ValueError("network endpoint port is invalid") from error
    if str(port) != port_text or not 1 <= port <= 65535:
        raise ValueError("network endpoint port is invalid")


class IntegrationNetworkAttachmentKind(StrEnum):
    LINUX_NAMESPACE = "linux_namespace"
    DOCKER_INTERNAL_NETWORK = "docker_internal_network"


@dataclass(frozen=True, slots=True)
class IntegrationNetworkEnforcementRequest:
    request_id: str
    environment_id: str
    permit_id: str
    exact_host_id: str
    principal_id: str
    session_id: str
    authority_ref: str
    signer_key_id: str
    signature_base64: str
    plan_sha256: str
    attachment_kinds: tuple[IntegrationNetworkAttachmentKind, ...]
    destinations: tuple[str, ...]
    maximum_network_bytes: int
    expires_at: datetime
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in (
            "request_id", "environment_id", "permit_id", "exact_host_id",
            "principal_id", "session_id", "authority_ref", "signer_key_id",
        ):
            text(getattr(self, name), name)
        digest(self.plan_sha256, "plan_sha256", required=True)
        try:
            signature = base64.b64decode(self.signature_base64, validate=True)
        except Exception as error:
            raise ValueError("network authority signature is invalid") from error
        if len(signature) != 64:
            raise ValueError("network authority signature is invalid")
        if (
            not self.attachment_kinds
            or any(not isinstance(item, IntegrationNetworkAttachmentKind) for item in self.attachment_kinds)
            or len(set(self.attachment_kinds)) != len(self.attachment_kinds)
        ):
            raise ValueError("network attachment kinds are invalid")
        texts(self.destinations, "network destinations")
        for destination in self.destinations:
            validate_integration_network_endpoint(destination)
        if not self.destinations:
            raise ValueError("network enforcement requires destinations")
        positive(self.maximum_network_bytes, "maximum_network_bytes")
        aware(self.expires_at, "network expires_at")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("integration network request version is unsupported")


@dataclass(frozen=True, slots=True)
class IntegrationNetworkAttachment:
    kind: IntegrationNetworkAttachmentKind
    attachment_reference: str
    proxy_uri: str

    def __post_init__(self) -> None:
        if not isinstance(self.kind, IntegrationNetworkAttachmentKind):
            raise ValueError("network attachment kind is invalid")
        text(self.attachment_reference, "attachment_reference")
        if not self.proxy_uri.startswith("http://") or "@" in self.proxy_uri:
            raise ValueError("network attachment proxy URI is invalid")


@dataclass(frozen=True, slots=True)
class IntegrationNetworkLease:
    enforcement_id: str
    request_id: str
    environment_id: str
    principal_id: str
    session_id: str
    authority_ref: str
    attachments: tuple[IntegrationNetworkAttachment, ...]
    destinations: tuple[str, ...]
    maximum_network_bytes: int
    issued_at: datetime
    expires_at: datetime
    evidence_sha256: str
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in (
            "enforcement_id", "request_id", "environment_id", "principal_id",
            "session_id", "authority_ref",
        ):
            text(getattr(self, name), name)
        if (
            not self.attachments
            or len({item.kind for item in self.attachments}) != len(self.attachments)
        ):
            raise ValueError("network lease attachments are invalid")
        texts(self.destinations, "network lease destinations")
        for destination in self.destinations:
            validate_integration_network_endpoint(destination)
        positive(self.maximum_network_bytes, "maximum_network_bytes")
        aware(self.issued_at, "network issued_at")
        aware(self.expires_at, "network expires_at")
        if self.expires_at <= self.issued_at:
            raise ValueError("network lease must expire after issue")
        digest(self.evidence_sha256, "network lease evidence", required=True)
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("integration network lease version is unsupported")


def validate_integration_network_lease(request, lease) -> None:
    if (
        lease.request_id != request.request_id
        or lease.environment_id != request.environment_id
        or lease.principal_id != request.principal_id
        or lease.session_id != request.session_id
        or lease.authority_ref != request.authority_ref
        or tuple(item.kind for item in lease.attachments) != request.attachment_kinds
        or lease.destinations != request.destinations
        or lease.maximum_network_bytes != request.maximum_network_bytes
        or lease.expires_at > request.expires_at
    ):
        raise ValueError("network lease differs from its exact request")


def integration_network_authority_payload(request) -> bytes:
    values = {
        "request_id": request.request_id,
        "environment_id": request.environment_id,
        "permit_id": request.permit_id,
        "exact_host_id": request.exact_host_id,
        "principal_id": request.principal_id,
        "session_id": request.session_id,
        "authority_ref": request.authority_ref,
        "signer_key_id": request.signer_key_id,
        "plan_sha256": request.plan_sha256,
        "attachment_kinds": [item.value for item in request.attachment_kinds],
        "destinations": list(request.destinations),
        "maximum_network_bytes": request.maximum_network_bytes,
        "expires_at": request.expires_at.isoformat(),
        "contract_version": request.contract_version,
    }
    return json.dumps(values, sort_keys=True, separators=(",", ":")).encode()


@dataclass(frozen=True, slots=True)
class IntegrationNetworkUsage:
    """A broker-issued snapshot of one environment's bounded network use."""

    enforcement_id: str
    environment_id: str
    destinations: tuple[str, ...]
    transmitted_bytes: int
    received_bytes: int
    maximum_network_bytes: int
    quota_exceeded: bool
    finalized: bool
    observed_at: datetime
    evidence_sha256: str
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        text(self.enforcement_id, "network enforcement_id")
        text(self.environment_id, "network environment_id")
        texts(self.destinations, "network destinations")
        for destination in self.destinations:
            validate_integration_network_endpoint(destination)
        positive(self.transmitted_bytes, "transmitted_bytes", allow_zero=True)
        positive(self.received_bytes, "received_bytes", allow_zero=True)
        positive(self.maximum_network_bytes, "maximum_network_bytes")
        aware(self.observed_at, "network observed_at")
        digest(self.evidence_sha256, "network evidence_sha256", required=True)
        if self.transmitted_bytes + self.received_bytes > self.maximum_network_bytes:
            raise ValueError("network usage exceeds its enforced byte limit")
        if self.quota_exceeded and not self.finalized:
            raise ValueError("an exceeded network quota must be finalized")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("integration network usage version is unsupported")


def validate_integration_network_usage(plan, usage, *, require_finalized: bool) -> None:
    """Bind trusted broker evidence to the exact admitted environment plan."""

    if usage is None:
        raise ValueError("allowlisted integration receipt requires network usage")
    if usage.environment_id != plan.environment_id:
        raise ValueError("network usage environment identity is mismatched")
    if usage.maximum_network_bytes != plan.resource_impact.max_network_bytes:
        raise ValueError("network usage byte limit differs from the admitted plan")
    if not set(usage.destinations).issubset(plan.network_hosts):
        raise ValueError("network usage contains an unapproved destination")
    if usage.quota_exceeded:
        raise ValueError("network quota exhaustion cannot produce a successful receipt")
    if require_finalized and not usage.finalized:
        raise ValueError("cleaned integration receipt requires finalized network usage")
