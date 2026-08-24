"""Truthful maturity contract for final product integration."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path

INTEGRATION_COVERAGE_VERSION = "fam.product.integration-coverage/v1alpha1"


class IntegrationMaturity(Enum):
    CONTRACT_ONLY = "contract_only"
    COMPONENT_TESTED = "component_tested"
    ACCEPTANCE_ONLY = "acceptance_only"
    SOURCE_COMPOSED = "source_composed"
    PRODUCTION_WIRED = "production_wired"
    INSTALLED_TESTED = "installed_tested"
    OPERATIONALLY_PROVEN = "operationally_proven"


class IntegrationProgramStatus(Enum):
    INTEGRATION_INCOMPLETE = "integration_incomplete"
    RELEASE_QUALIFICATION = "release_qualification"
    COMPLETE = "complete"


@dataclass(frozen=True, slots=True)
class IntegrationCoverageItem:
    subsystem_id: str
    maturity: IntegrationMaturity
    target_maturity: IntegrationMaturity
    production_reachable: bool
    installed_evidence: bool
    evidence_refs: tuple[str, ...]
    known_gaps: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.subsystem_id or not self.evidence_refs:
            raise ValueError("coverage item identity and evidence must not be empty")
        if self.maturity is IntegrationMaturity.OPERATIONALLY_PROVEN:
            if not self.production_reachable or not self.installed_evidence:
                raise ValueError("operational maturity requires installed production evidence")


@dataclass(frozen=True, slots=True)
class IntegrationCoverageManifest:
    observed_at: datetime
    program_status: IntegrationProgramStatus
    items: tuple[IntegrationCoverageItem, ...]
    contract_version: str = INTEGRATION_COVERAGE_VERSION

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None:
            raise ValueError("coverage observation must include a timezone")
        if self.contract_version != INTEGRATION_COVERAGE_VERSION:
            raise ValueError("unsupported integration coverage version")
        identities = tuple(item.subsystem_id for item in self.items)
        if not identities or len(set(identities)) != len(identities):
            raise ValueError("coverage subsystem IDs must be present and unique")
        if self.program_status is IntegrationProgramStatus.COMPLETE:
            if not all(_complete(item) for item in self.items):
                raise ValueError("complete status requires operational evidence for every subsystem")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def load_integration_coverage(path: Path) -> IntegrationCoverageManifest:
    from fam_os.schemas.codec import loads_document

    value = loads_document(path.read_text(encoding="utf-8"))
    if not isinstance(value, IntegrationCoverageManifest):
        raise TypeError("document is not an integration coverage manifest")
    return value


def _complete(item: IntegrationCoverageItem) -> bool:
    return (
        item.maturity is IntegrationMaturity.OPERATIONALLY_PROVEN
        and item.production_reachable
        and item.installed_evidence
        and not item.known_gaps
    )
