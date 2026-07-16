"""Schema identity and alpha compatibility policy."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import re


_ALPHA_VERSION = re.compile(r"/v1alpha[1-9][0-9]*$")


class CompatibilityPolicy(StrEnum):
    """How a decoder admits serialized schema versions."""

    EXACT = "exact"


@dataclass(frozen=True, slots=True)
class SchemaDescriptor:
    """One self-describing wire document and its domain root type."""

    schema_id: str
    contract_version: str
    root_type: type[object]
    title: str
    compatibility: CompatibilityPolicy = CompatibilityPolicy.EXACT

    def __post_init__(self) -> None:
        for field_name in ("schema_id", "contract_version", "title"):
            if not getattr(self, field_name).strip():
                raise ValueError(f"{field_name} must not be empty")
        if "/" not in self.schema_id or not _ALPHA_VERSION.search(self.schema_id):
            raise ValueError("schema_id must have a versioned v1alpha identity")
        if not _ALPHA_VERSION.search(self.contract_version):
            raise ValueError("contract_version must identify a v1alpha version")

    @property
    def family_id(self) -> str:
        return self.schema_id.rsplit("/", 1)[0]
