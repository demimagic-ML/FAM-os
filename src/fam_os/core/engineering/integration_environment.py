"""Bounded service, browser, container, and local-cluster environments."""

from dataclasses import dataclass
from dataclasses import asdict
from datetime import datetime
from enum import StrEnum
import hashlib
import json

from fam_os.core.engineering._validation import (
    absolute_path, aware, digest, positive, relative_path, text, texts,
)
from fam_os.core.engineering.authority import EngineeringAuthority
from fam_os.core.engineering.grants import EngineeringResourceImpact
from fam_os.core.engineering.version import ENGINEERING_CONTRACT_VERSION
from fam_os.core.engineering.integration_network import (
    IntegrationNetworkEnforcementRequest,
    IntegrationNetworkLease,
    validate_integration_network_lease,
    validate_integration_network_endpoint,
)


class IntegrationServiceKind(StrEnum):
    PROCESS = "process"
    API = "api"
    BROWSER = "browser"
    CONTAINER = "container"
    CLUSTER_CONTROL_PLANE = "cluster_control_plane"


class IntegrationNetworkMode(StrEnum):
    DENIED = "denied"
    ISOLATED = "isolated"
    ALLOWLIST = "allowlist"


class IntegrationHealthKind(StrEnum):
    TCP = "tcp"
    HTTP = "http"
    SIGNED_RECIPE = "signed_recipe"


class IntegrationEnvironmentStatus(StrEnum):
    READY = "ready"
    FAILED = "failed"
    CLEANED = "cleaned"


@dataclass(frozen=True, slots=True)
class IntegrationPortBinding:
    name: str
    container_port: int
    requested_host_port: int
    protocol: str = "tcp"
    host_address: str = "127.0.0.1"

    def __post_init__(self) -> None:
        text(self.name, "port name")
        positive(self.container_port, "container_port")
        positive(self.requested_host_port, "requested_host_port", allow_zero=True)
        if self.container_port > 65535 or self.requested_host_port > 65535:
            raise ValueError("integration port is outside TCP/UDP range")
        if self.protocol not in {"tcp", "udp"}:
            raise ValueError("integration port protocol is unsupported")
        if self.host_address != "127.0.0.1":
            raise ValueError("integration host ports must bind loopback")


@dataclass(frozen=True, slots=True)
class IntegrationVolumeMount:
    volume_id: str
    candidate_relative_path: str
    mount_path: str
    read_only: bool
    maximum_bytes: int
    retain_artifacts: bool = False

    def __post_init__(self) -> None:
        text(self.volume_id, "volume_id")
        relative_path(self.candidate_relative_path, "candidate_relative_path")
        absolute_path(self.mount_path, "mount_path")
        if self.mount_path == "/":
            raise ValueError("integration volume cannot mount over container root")
        positive(self.maximum_bytes, "maximum_bytes")


@dataclass(frozen=True, slots=True)
class IntegrationHealthCheck:
    kind: IntegrationHealthKind
    port_name: str | None
    path: str | None
    signed_recipe_id: str | None
    interval_seconds: int
    timeout_seconds: int
    maximum_attempts: int

    def __post_init__(self) -> None:
        if not isinstance(self.kind, IntegrationHealthKind):
            raise ValueError("integration health kind is invalid")
        positive(self.interval_seconds, "health interval_seconds")
        positive(self.timeout_seconds, "health timeout_seconds")
        positive(self.maximum_attempts, "health maximum_attempts")
        if self.timeout_seconds > self.interval_seconds:
            raise ValueError("health timeout cannot exceed interval")
        if self.kind in {IntegrationHealthKind.TCP, IntegrationHealthKind.HTTP}:
            if self.port_name is None or self.signed_recipe_id is not None:
                raise ValueError("network health check requires only a port")
            text(self.port_name, "health port_name")
        elif self.kind is IntegrationHealthKind.SIGNED_RECIPE:
            if self.signed_recipe_id is None or self.port_name is not None or self.path is not None:
                raise ValueError("recipe health check requires only a signed recipe")
            text(self.signed_recipe_id, "health signed_recipe_id")
        if self.kind is IntegrationHealthKind.HTTP:
            if self.path is None or not self.path.startswith("/") or ".." in self.path:
                raise ValueError("HTTP health path must be absolute and normalized")
        elif self.path is not None:
            raise ValueError("only HTTP health checks accept a path")


@dataclass(frozen=True, slots=True)
class IntegrationServiceSpec:
    service_id: str
    kind: IntegrationServiceKind
    signed_launch_recipe_id: str | None
    launch_arguments: tuple[str, ...]
    image_ref: str | None
    image_sha256: str | None
    ports: tuple[IntegrationPortBinding, ...]
    volumes: tuple[IntegrationVolumeMount, ...]
    health_check: IntegrationHealthCheck
    dependency_ids: tuple[str, ...]
    secret_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        text(self.service_id, "service_id")
        if not isinstance(self.kind, IntegrationServiceKind):
            raise ValueError("integration service kind is invalid")
        texts(self.launch_arguments, "launch_arguments", unique=False)
        texts(self.dependency_ids, "dependency_ids")
        texts(self.secret_refs, "secret_refs")
        container = self.kind in {
            IntegrationServiceKind.CONTAINER,
            IntegrationServiceKind.CLUSTER_CONTROL_PLANE,
        }
        if container:
            if self.image_ref is None or self.image_sha256 is None or self.signed_launch_recipe_id is not None:
                raise ValueError("container service requires only a digest-bound image")
            text(self.image_ref, "image_ref")
            digest(self.image_sha256, "image_sha256", required=True)
        elif self.signed_launch_recipe_id is None or self.image_ref is not None or self.image_sha256 is not None:
            raise ValueError("process service requires only a signed launch recipe")
        else:
            text(self.signed_launch_recipe_id, "signed_launch_recipe_id")
        _unique_members(self.ports, "name", "service port")
        _unique_members(self.volumes, "volume_id", "service volume")
        if len({item.mount_path for item in self.volumes}) != len(self.volumes):
            raise ValueError("service volume mount paths must be unique")
        if len({item.candidate_relative_path for item in self.volumes}) != len(self.volumes):
            raise ValueError("service volume candidate paths must be unique")
        if self.health_check.port_name is not None and self.health_check.port_name not in {
            item.name for item in self.ports
        }:
            raise ValueError("health check references an undeclared port")


@dataclass(frozen=True, slots=True)
class IntegrationEnvironmentPlan:
    environment_id: str
    task_id: str
    candidate_id: str
    approved_changeset_id: str
    exact_host_id: str
    candidate_root: str
    services: tuple[IntegrationServiceSpec, ...]
    network_mode: IntegrationNetworkMode
    network_hosts: tuple[str, ...]
    retained_artifact_paths: tuple[str, ...]
    resource_impact: EngineeringResourceImpact
    maximum_memory_bytes: int
    maximum_cpu_millis_per_second: int
    required_authorities: tuple[EngineeringAuthority, ...]
    cleanup_required: bool
    created_at: datetime
    expires_at: datetime
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in (
            "environment_id", "task_id", "candidate_id",
            "approved_changeset_id", "exact_host_id",
        ):
            text(getattr(self, name), name)
        absolute_path(self.candidate_root, "candidate_root")
        if not isinstance(self.network_mode, IntegrationNetworkMode):
            raise ValueError("integration network mode is invalid")
        if not self.services:
            raise ValueError("integration environment requires services")
        _unique_members(self.services, "service_id", "environment service")
        service_ids = {item.service_id for item in self.services}
        if any(
            dependency not in service_ids or dependency == item.service_id
            for item in self.services for dependency in item.dependency_ids
        ):
            raise ValueError("integration service dependency is invalid")
        _require_acyclic(self.services)
        texts(self.network_hosts, "network_hosts")
        for endpoint in self.network_hosts:
            validate_integration_network_endpoint(endpoint)
        for path in self.retained_artifact_paths:
            relative_path(path, "retained_artifact_paths item")
        texts(self.retained_artifact_paths, "retained_artifact_paths")
        if (self.network_mode is IntegrationNetworkMode.ALLOWLIST) != bool(self.network_hosts):
            raise ValueError("integration network allowlist and hosts disagree")
        secret_refs = {value for item in self.services for value in item.secret_refs}
        expected = {EngineeringAuthority.EXECUTE}
        if self.network_hosts:
            expected.add(EngineeringAuthority.NETWORK)
        if secret_refs:
            expected.add(EngineeringAuthority.SECRET_USE)
        canonical = tuple(item for item in EngineeringAuthority if item in expected)
        if self.required_authorities != canonical:
            raise ValueError("integration environment authorities are not exact")
        if self.resource_impact.max_processes < len(self.services):
            raise ValueError("integration process budget is below service count")
        positive(self.maximum_memory_bytes, "maximum_memory_bytes")
        positive(
            self.maximum_cpu_millis_per_second,
            "maximum_cpu_millis_per_second",
        )
        volume_bytes = sum(
            volume.maximum_bytes
            for service in self.services for volume in service.volumes
        )
        if volume_bytes > self.resource_impact.max_changed_bytes:
            raise ValueError("integration volume budget exceeds changed-byte limit")
        if self.network_mode is IntegrationNetworkMode.DENIED and self.resource_impact.max_network_bytes:
            raise ValueError("network-denied integration budget must be zero")
        if (
            self.network_mode is IntegrationNetworkMode.ALLOWLIST
            and self.resource_impact.max_network_bytes <= 0
        ):
            raise ValueError("allowlisted integration requires a positive network byte budget")
        if not self.cleanup_required:
            raise ValueError("integration environments require cleanup")
        aware(self.created_at, "created_at")
        aware(self.expires_at, "expires_at")
        if self.expires_at <= self.created_at:
            raise ValueError("integration environment must expire")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("integration environment plan version is unsupported")


@dataclass(frozen=True, slots=True)
class IntegrationExecutionPermit:
    permit_id: str
    environment_id: str
    approved_changeset_id: str
    exact_host_id: str
    authorization_decision_ids: tuple[str, ...]
    issued_at: datetime
    expires_at: datetime
    network_request: IntegrationNetworkEnforcementRequest | None = None
    network_lease: IntegrationNetworkLease | None = None
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in ("permit_id", "environment_id", "approved_changeset_id", "exact_host_id"):
            text(getattr(self, name), name)
        texts(self.authorization_decision_ids, "authorization_decision_ids")
        if not self.authorization_decision_ids:
            raise ValueError("integration permit requires authorization decisions")
        aware(self.issued_at, "issued_at")
        aware(self.expires_at, "expires_at")
        if self.expires_at <= self.issued_at:
            raise ValueError("integration permit must expire")
        if self.network_request is not None and (
            self.network_request.environment_id != self.environment_id
            or self.network_request.permit_id != self.permit_id
            or self.network_request.exact_host_id != self.exact_host_id
            or self.network_request.expires_at > self.expires_at
        ):
            raise ValueError("integration permit network request is mismatched")
        if self.network_lease is not None:
            if self.network_request is None:
                raise ValueError("integration network lease requires its request")
            validate_integration_network_lease(
                self.network_request, self.network_lease,
            )
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("integration execution permit version is unsupported")


def _unique_members(values, attribute: str, label: str) -> None:
    identities = tuple(getattr(item, attribute) for item in values)
    if len(set(identities)) != len(identities):
        raise ValueError(f"{label} identities must be unique")


def _require_acyclic(services: tuple[IntegrationServiceSpec, ...]) -> None:
    dependencies = {item.service_id: set(item.dependency_ids) for item in services}
    remaining = set(dependencies)
    while remaining:
        ready = {item for item in remaining if not dependencies[item] & remaining}
        if not ready:
            raise ValueError("integration service dependencies contain a cycle")
        remaining -= ready


def integration_environment_plan_digest(plan: IntegrationEnvironmentPlan) -> str:
    def value(item):
        if isinstance(item, datetime):
            return item.isoformat()
        if isinstance(item, StrEnum):
            return item.value
        if isinstance(item, dict):
            return {key: value(member) for key, member in item.items()}
        if isinstance(item, (tuple, list)):
            return [value(member) for member in item]
        return item

    payload = json.dumps(
        value(asdict(plan)), sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
