"""Exact natural integration resources kept outside ordinary task authority."""

from datetime import datetime
import re

from fam_os.core.engineering.authority import EngineeringAuthority
from fam_os.core.engineering.delegation import EngineeringDelegationMode
from fam_os.core.engineering.grants import (
    EngineeringAuthorityGrant,
    EngineeringGrantScope,
    EngineeringGrantScopeKind,
    EngineeringResourceImpact,
    GrantLifecycleState,
    ReversibilityPolicy,
    SecretExposurePolicy,
    VerificationRequirement,
)
from fam_os.core.engineering.integration_network import (
    validate_integration_network_endpoint,
)


INTEGRATION_RESOURCE_AUTHORITIES = frozenset({
    EngineeringAuthority.NETWORK,
    EngineeringAuthority.SECRET_USE,
})
_NETWORK_ENDPOINT = re.compile(
    r"\b(?:network|internet)\s+(?:access\s+)?(?:to|host|destination)\s+"
    r"((?:\[[0-9a-fA-F:]+\]|"
    r"[a-zA-Z0-9](?:[a-zA-Z0-9.-]{0,252})):[0-9]{1,5})(?![0-9])",
    re.IGNORECASE,
)
_SECRET_REFERENCE = re.compile(
    r"\bsecret\s+(?:reference|ref|named)\s+[\"'`]?"
    r"([a-zA-Z0-9](?:[a-zA-Z0-9._/-]{0,126}[a-zA-Z0-9])?)",
    re.IGNORECASE,
)
_INTEGRATION_NETWORK_BUDGET_BYTES = 16 * 1024**2
_POSTGRESQL_STORAGE_BUDGET_BYTES = 256 * 1024**2
_POSTGRESQL_SERVICE = re.compile(
    r"\b(?:postgresql|postgres)\s+(?:service|container)|"
    r"\b(?:run|start|launch|test)\s+(?:a\s+|the\s+)?"
    r"(?:postgresql|postgres)(?:\s+(?:service|container|database))?\b",
    re.IGNORECASE,
)


def natural_integration_resource_grant_id(primary_grant_id: str) -> str:
    if not isinstance(primary_grant_id, str) or not primary_grant_id.strip():
        raise ValueError("primary natural engineering grant identity is empty")
    return f"{primary_grant_id}-integration-resources"


def natural_integration_resource_scope(
    intent: str,
    requested_authorities: tuple[EngineeringAuthority, ...] | None = None,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Extract only explicit canonical endpoints and opaque reference names."""

    requested = (
        _resource_authorities(intent)
        if requested_authorities is None else tuple(
            item for item in requested_authorities
            if item in INTEGRATION_RESOURCE_AUTHORITIES
        )
    )
    network_requested = EngineeringAuthority.NETWORK in requested
    secret_requested = EngineeringAuthority.SECRET_USE in requested
    endpoints = tuple(dict.fromkeys(
        match.group(1) for match in _NETWORK_ENDPOINT.finditer(intent)
    ))
    for endpoint in endpoints:
        validate_integration_network_endpoint(endpoint)
    secret_refs = tuple(dict.fromkeys(
        match.group(1) for match in _SECRET_REFERENCE.finditer(intent)
    ))
    if network_requested and not endpoints:
        raise ValueError(
            "natural integration network access requires an explicit canonical host:port"
        )
    if secret_requested and not secret_refs:
        raise ValueError(
            "natural integration secret use requires an explicit secret ref"
        )
    return (
        endpoints if network_requested else (),
        secret_refs if secret_requested else (),
    )


def natural_integration_resource_impact(
    intent: str, network_hosts: tuple[str, ...],
) -> EngineeringResourceImpact:
    """Return the complete immutable supplemental integration budget."""

    if not isinstance(intent, str):
        raise ValueError("natural integration intent is invalid")
    return EngineeringResourceImpact(
        600, 16, 64, 0,
        (
            _POSTGRESQL_STORAGE_BUDGET_BYTES
            if _POSTGRESQL_SERVICE.search(intent) else 0
        ),
        _INTEGRATION_NETWORK_BUDGET_BYTES if network_hosts else 0,
    )


def build_natural_integration_resource_grant(
    intent: str,
    primary: EngineeringAuthorityGrant,
    task,
    requested_authorities: tuple[EngineeringAuthority, ...],
    issued_at: datetime,
    expires_at: datetime,
) -> EngineeringAuthorityGrant | None:
    requested = tuple(
        item for item in requested_authorities
        if item in INTEGRATION_RESOURCE_AUTHORITIES
    )
    if not requested:
        return None
    try:
        network_hosts, secret_refs = natural_integration_resource_scope(
            intent, requested,
        )
    except ValueError:
        return None
    authorities = tuple(
        item for item in EngineeringAuthority
        if item is EngineeringAuthority.EXECUTE or item in requested
    )
    scope = EngineeringGrantScope(
        EngineeringGrantScopeKind.TASK, task.task_id, task.workspace_roots,
        (), (), ("integration-environment",), network_hosts, (), (), (),
        secret_refs,
    )
    impact = natural_integration_resource_impact(intent, network_hosts)
    return EngineeringAuthorityGrant(
        natural_integration_resource_grant_id(primary.grant_id),
        primary.owner_id, primary.principal_id, EngineeringDelegationMode.CUSTOM,
        authorities, scope,
        f"Natural integration resources for {task.task_id}", issued_at,
        expires_at, GrantLifecycleState.ACTIVE, ReversibilityPolicy.REQUIRED,
        (
            SecretExposurePolicy.OPAQUE_CREDENTIAL_INJECTION
            if secret_refs else SecretExposurePolicy.NONE
        ),
        VerificationRequirement.REQUIRED, impact,
    )


def _resource_authorities(intent: str) -> tuple[EngineeringAuthority, ...]:
    normalized = " ".join(intent.casefold().split())
    values = []
    if re.search(r"\b(fetch|download|network|internet|registry)\b", normalized):
        values.append(EngineeringAuthority.NETWORK)
    if re.search(
        r"\b(secret|credential|password|api key|token)\b", normalized,
    ):
        values.append(EngineeringAuthority.SECRET_USE)
    return tuple(values)
