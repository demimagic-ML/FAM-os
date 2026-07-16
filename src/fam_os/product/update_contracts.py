"""Versioned all-component release update contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


UPDATE_CONTRACT_VERSION = "fam.product.update/v1alpha1"


class ComponentKind(StrEnum):
    SERVICE = "service"
    SCHEMA = "schema"
    EXPERT = "expert"
    CONNECTOR = "connector"


@dataclass(frozen=True, slots=True)
class ReleaseComponent:
    kind: ComponentKind
    name: str
    source_path: str
    sha256: str

    def __post_init__(self) -> None:
        if not self.name or len(self.sha256) != 64:
            raise ValueError("release component requires name and SHA-256")


@dataclass(frozen=True, slots=True)
class SignedReleaseManifest:
    release_id: str
    components: tuple[ReleaseComponent, ...]
    signer_key_id: str
    signature_base64: str
    contract_version: str = UPDATE_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != UPDATE_CONTRACT_VERSION:
            raise ValueError("unsupported update contract version")
        kinds = {item.kind for item in self.components}
        if kinds != set(ComponentKind):
            raise ValueError("release must contain every component kind")
        identities = tuple((item.kind, item.name) for item in self.components)
        if len(set(identities)) != len(identities):
            raise ValueError("release components must be unique")


@dataclass(frozen=True, slots=True)
class UpdateReceipt:
    release_id: str
    previous_release_id: str | None
    staged: bool
    health_checked: bool
    activated: bool
    rolled_back: bool
    active_release_id: str | None
    reason: str
    contract_version: str = UPDATE_CONTRACT_VERSION
