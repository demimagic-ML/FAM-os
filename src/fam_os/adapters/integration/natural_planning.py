"""Deterministic natural-language planning for local web preview environments."""

from datetime import datetime, timedelta
import hashlib
from pathlib import Path

from fam_os.adapters.integration.natural_resource_planning import (
    natural_resource_scope,
)
from fam_os.adapters.integration.natural_template_selection import (
    natural_integration_templates,
)
from fam_os.adapters.integration.natural_template_identity import (
    PYTHON_API_RECIPE_ID,
    STATIC_SITE_RECIPE_ID,
)
from fam_os.adapters.integration.postgresql_template import (
    POSTGRESQL_VOLUME_BYTES,
    postgresql_service_spec,
)
from fam_os.core.engineering import (
    EngineeringAuthority,
    EngineeringResourceImpact,
    IntegrationEnvironmentPlan,
    IntegrationHealthCheck,
    IntegrationHealthKind,
    IntegrationNetworkMode,
    IntegrationPortBinding,
    IntegrationServiceKind,
    IntegrationServiceSpec,
    NaturalIntegrationServiceTemplate,
    natural_integration_environment_requested,
)


ROOT_PYTHON_API_RECIPE = PYTHON_API_RECIPE_ID
STATIC_PREVIEW_RECIPE = STATIC_SITE_RECIPE_ID


class NaturalIntegrationEnvironmentPlanner:
    """Create exact plans from templates and separately approved resources."""

    def __init__(self, exact_host_id: str) -> None:
        if not exact_host_id.strip():
            raise ValueError("natural integration host identity is empty")
        self._exact_host_id = exact_host_id

    @staticmethod
    def requested(intent: str) -> bool:
        return natural_integration_environment_requested(intent)

    def required_port_count(self, definition, candidate, changed_paths) -> int:
        return sum(
            declaration.template is not NaturalIntegrationServiceTemplate.POSTGRESQL
            for declaration, _health_path in natural_integration_templates(
                definition, candidate, changed_paths,
            )
        )

    def build(
        self, definition, candidate, changed_paths, changeset_id: str,
        host_port: int | tuple[int, ...], *, postapply: bool, now: datetime,
        resource_grant=None,
    ) -> IntegrationEnvironmentPlan:
        task = definition.task
        if not self.requested(task.intent):
            raise ValueError("natural integration environment was not requested")
        if EngineeringAuthority.EXECUTE not in task.authorities:
            raise PermissionError("natural integration environment requires execute authority")
        if task.task_id != candidate.task_id:
            raise ValueError("natural integration candidate task is mismatched")
        root = Path(candidate.candidate_workspace)
        if root.is_symlink() or not root.is_dir() or root.resolve() != root:
            raise PermissionError("natural integration candidate root is invalid")
        templates = natural_integration_templates(
            definition, candidate, tuple(changed_paths),
        )
        network_hosts, secret_bindings, network_bytes = natural_resource_scope(
            definition, resource_grant, now, templates,
        )
        ports = _ports(host_port, sum(
            declaration.template is not NaturalIntegrationServiceTemplate.POSTGRESQL
            for declaration, _health_path in templates
        ))
        phase = "postapply" if postapply else "candidate"
        identity = _identity(task.task_id, phase)
        services = _services(templates, ports, phase, secret_bindings)
        postgres = any(
            item.template is NaturalIntegrationServiceTemplate.POSTGRESQL
            for item, _health_path in templates
        )
        authorities = tuple(
            item for item in EngineeringAuthority
            if (
                item is EngineeringAuthority.EXECUTE
                or item is EngineeringAuthority.NETWORK and network_hosts
                or item is EngineeringAuthority.SECRET_USE and secret_bindings
            )
        )
        impact = EngineeringResourceImpact(
            120, len(services) + 1,
            (64 if postgres else max(4, len(services) * 4)), 0,
            (POSTGRESQL_VOLUME_BYTES if postgres else 0),
            network_bytes,
        )
        return IntegrationEnvironmentPlan(
            identity, task.task_id, candidate.candidate_id, changeset_id,
            self._exact_host_id, str(root), services,
            (
                IntegrationNetworkMode.ALLOWLIST
                if network_hosts else IntegrationNetworkMode.ISOLATED
            ),
            network_hosts, (), impact,
            (536_870_912 if postgres else 134_217_728),
            (1000 if postgres else 50), authorities, True,
            now, min(task.expires_at, now + timedelta(minutes=10)),
        )

def natural_integration_environment_id(task_id: str, *, postapply: bool) -> str:
    return _identity(task_id, "postapply" if postapply else "candidate")


def _identity(task_id: str, phase: str) -> str:
    value = hashlib.sha256(f"{task_id}:{phase}:static-preview-v1".encode()).hexdigest()
    return f"natural-integration-{phase}-{value[:24]}"


def _ports(value: int | tuple[int, ...], count: int) -> tuple[int, ...]:
    values = (value,) if isinstance(value, int) else tuple(value)
    if len(values) != count or len(set(values)) != count:
        raise ValueError("natural integration requires one unique port per service")
    if any(item < 1 or item > 65535 for item in values):
        raise ValueError("natural integration port is outside TCP range")
    return values


def _services(templates, ports, phase, secret_bindings=None):
    secret_bindings = secret_bindings or {}
    values = []
    service_ids = {
        item.service_id: f"{item.service_id}-{phase}"
        for item, _health_path in templates
    }
    port_values = iter(ports)
    for declaration, health_path in templates:
        service_id = service_ids[declaration.service_id]
        dependencies = tuple(
            service_ids[item] for item in declaration.dependency_ids
        )
        secret_refs = secret_bindings.get(declaration.template, ())
        if declaration.template is NaturalIntegrationServiceTemplate.POSTGRESQL:
            values.append(postgresql_service_spec(
                service_id, dependencies, secret_refs,
            ))
            continue
        port = next(port_values)
        if declaration.template is NaturalIntegrationServiceTemplate.PYTHON_API:
            values.append(IntegrationServiceSpec(
                service_id, IntegrationServiceKind.API, PYTHON_API_RECIPE_ID,
                ("/workspace/api.py", str(port)), None, None,
                (IntegrationPortBinding("api", port, port),), (),
                IntegrationHealthCheck(
                    IntegrationHealthKind.HTTP, "api", health_path, None,
                    1, 1, 15,
                ),
                dependencies, secret_refs,
            ))
        else:
            values.append(IntegrationServiceSpec(
                service_id, IntegrationServiceKind.API,
                STATIC_SITE_RECIPE_ID,
                (
                    "-m", "http.server", str(port), "--bind",
                    "127.0.0.1", "--directory", "/workspace",
                ),
                None, None,
                (IntegrationPortBinding("preview", port, port),), (),
                IntegrationHealthCheck(
                    IntegrationHealthKind.HTTP, "preview", health_path, None,
                    1, 1, 15,
                ),
                dependencies, (),
            ))
    try:
        next(port_values)
    except StopIteration:
        pass
    else:
        raise ValueError("natural integration has unused allocated ports")
    return tuple(values)
