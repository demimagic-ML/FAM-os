"""Map one separately approved natural resource grant into an exact plan."""

import re

from fam_os.core.engineering import (
    EngineeringAuthority,
    NaturalIntegrationServiceTemplate,
    natural_integration_resource_grant_id,
    natural_integration_resource_impact,
    natural_integration_resource_scope,
)
from fam_os.core.engineering.grants import (
    EngineeringGrantScopeKind,
    SecretExposurePolicy,
)


_SCOPED_SECRET_REFERENCE = re.compile(
    r"\b(python\s+api|api|postgresql|postgres|database)\s+secret\s+"
    r"(?:reference|ref|named)\s+[\"'`]?"
    r"([a-zA-Z0-9](?:[a-zA-Z0-9._/-]{0,126}[a-zA-Z0-9])?)",
    re.IGNORECASE,
)


def natural_resource_scope(definition, grant, now, templates):
    task = definition.task
    network_hosts, secret_refs = natural_integration_resource_scope(task.intent)
    if not network_hosts and not secret_refs:
        if grant is not None:
            raise PermissionError(
                "natural integration resource grant exceeds the admitted intent"
            )
        return (), _secret_bindings(task.intent, (), templates), 0
    if grant is None:
        raise PermissionError(
            "natural integration resources require separate owner approval"
        )
    expected_authorities = tuple(
        item for item in EngineeringAuthority
        if (
            item is EngineeringAuthority.EXECUTE
            or item is EngineeringAuthority.NETWORK and network_hosts
            or item is EngineeringAuthority.SECRET_USE and secret_refs
        )
    )
    scope = grant.scope
    if (
        grant.grant_id != natural_integration_resource_grant_id(task.grant_id)
        or grant.owner_id != task.owner_id
        or grant.principal_id != task.owner_id
        or grant.authorities != expected_authorities
        or not grant.active_at(now)
        or scope.kind is not EngineeringGrantScopeKind.TASK
        or scope.scope_id != task.task_id
        or scope.workspace_roots != task.workspace_roots
        or scope.path_allowlist
        or scope.path_denylist
        or scope.toolchains != ("integration-environment",)
        or scope.network_hosts != network_hosts
        or scope.package_registries
        or scope.git_remotes
        or scope.git_branches
        or scope.secret_refs != secret_refs
        or grant.resource_impact
        != natural_integration_resource_impact(task.intent, network_hosts)
        or grant.secret_exposure is not (
            SecretExposurePolicy.OPAQUE_CREDENTIAL_INJECTION
            if secret_refs else SecretExposurePolicy.NONE
        )
    ):
        raise PermissionError(
            "natural integration resource grant differs from exact intent"
        )
    bindings = _secret_bindings(task.intent, secret_refs, templates)
    network_bytes = grant.resource_impact.max_network_bytes
    return network_hosts, bindings, network_bytes


def _secret_bindings(intent, secret_refs, templates):
    present = {
        declaration.template for declaration, _health_path in templates
    }
    consumers = present.intersection({
        NaturalIntegrationServiceTemplate.PYTHON_API,
        NaturalIntegrationServiceTemplate.POSTGRESQL,
    })
    if not secret_refs:
        if NaturalIntegrationServiceTemplate.POSTGRESQL in present:
            raise PermissionError(
                "natural PostgreSQL requires an explicit opaque secret ref"
            )
        return {}
    if not consumers:
        raise PermissionError(
            "natural integration secret refs require a secret-capable service"
        )
    scoped = {}
    for match in _SCOPED_SECRET_REFERENCE.finditer(intent):
        role = _secret_role(match.group(1))
        reference = match.group(2)
        prior = scoped.get(reference)
        if prior is not None and prior is not role:
            raise PermissionError(
                "one natural secret ref cannot target multiple service roles"
            )
        scoped[reference] = role
    if len(consumers) == 1:
        consumer = next(iter(consumers))
        if any(role is not consumer for role in scoped.values()):
            raise PermissionError(
                "natural secret role is absent from the declared environment"
            )
        bindings = {consumer: tuple(secret_refs)}
    else:
        if set(scoped) != set(secret_refs):
            raise PermissionError(
                "multi-service natural secrets require an explicit service role"
            )
        if any(role not in consumers for role in scoped.values()):
            raise PermissionError(
                "natural secret role is absent from the declared environment"
            )
        bindings = {
            consumer: tuple(
                reference for reference in secret_refs
                if scoped[reference] is consumer
            )
            for consumer in consumers
        }
    postgres = bindings.get(NaturalIntegrationServiceTemplate.POSTGRESQL, ())
    if (
        NaturalIntegrationServiceTemplate.POSTGRESQL in present
        and len(postgres) != 1
    ):
        raise PermissionError(
            "natural PostgreSQL requires exactly one opaque password secret ref"
        )
    return bindings


def _secret_role(value):
    return (
        NaturalIntegrationServiceTemplate.POSTGRESQL
        if value.casefold() in {"postgresql", "postgres", "database"}
        else NaturalIntegrationServiceTemplate.PYTHON_API
    )
