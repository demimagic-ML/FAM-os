"""Versioned declarative vocabulary for natural integration environments."""

from dataclasses import dataclass
from enum import StrEnum
import re

from fam_os.core.engineering._validation import text, texts
from fam_os.core.engineering.version import ENGINEERING_CONTRACT_VERSION


NATURAL_INTEGRATION_DECLARATION_PATH = "fam.integration.json"
NATURAL_INTEGRATION_DECLARATION_SCHEMA_ID = (
    "fam.core.natural-integration-declaration/v1alpha1"
)
_SERVICE_ID = re.compile(r"[a-z][a-z0-9-]{0,47}\Z")


class NaturalIntegrationServiceTemplate(StrEnum):
    PYTHON_API = "python_api"
    STATIC_SITE = "static_site"
    POSTGRESQL = "postgresql"


@dataclass(frozen=True, slots=True)
class NaturalIntegrationServiceDeclaration:
    service_id: str
    template: NaturalIntegrationServiceTemplate
    dependency_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        text(self.service_id, "natural integration service_id")
        if _SERVICE_ID.fullmatch(self.service_id) is None:
            raise ValueError("natural integration service_id is invalid")
        if not isinstance(self.template, NaturalIntegrationServiceTemplate):
            raise ValueError("natural integration service template is invalid")
        texts(self.dependency_ids, "natural integration dependency_ids")
        if len(self.dependency_ids) > 7:
            raise ValueError("natural integration service has too many dependencies")


@dataclass(frozen=True, slots=True)
class NaturalIntegrationEnvironmentDeclaration:
    declaration_id: str
    services: tuple[NaturalIntegrationServiceDeclaration, ...]
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        text(self.declaration_id, "natural integration declaration_id")
        if not 0 < len(self.services) <= 8:
            raise ValueError("natural integration declaration service count is invalid")
        identities = tuple(item.service_id for item in self.services)
        texts(identities, "natural integration service identities")
        templates = tuple(item.template for item in self.services)
        if len(set(templates)) != len(templates):
            raise ValueError("natural integration fixed templates cannot repeat")
        known = set(identities)
        if any(
            dependency not in known or dependency == item.service_id
            for item in self.services for dependency in item.dependency_ids
        ):
            raise ValueError("natural integration dependency is invalid")
        _require_acyclic(self.services)
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("natural integration declaration version is unsupported")


def _require_acyclic(services) -> None:
    dependencies = {
        item.service_id: set(item.dependency_ids) for item in services
    }
    remaining = set(dependencies)
    while remaining:
        ready = {
            item for item in remaining
            if not dependencies[item].intersection(remaining)
        }
        if not ready:
            raise ValueError("natural integration dependencies contain a cycle")
        remaining.difference_update(ready)
