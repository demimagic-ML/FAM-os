"""Application capability descriptions and registry entries."""

from __future__ import annotations

from dataclasses import dataclass

from fam_os.applications.identifiers import (
    normalize_unique,
    require_identifier,
    require_text,
)
from fam_os.applications.policy import (
    ApplicationAuthority,
    CapabilityKind,
    ConfirmationPolicy,
    Reversibility,
)


@dataclass(frozen=True, slots=True)
class CapabilityDescriptor:
    capability_id: str
    display_name: str
    description: str
    kind: CapabilityKind
    required_authority: ApplicationAuthority
    input_schema_id: str
    output_schema_id: str
    reversibility: Reversibility = Reversibility.NOT_APPLICABLE
    confirmation: ConfirmationPolicy = ConfirmationPolicy.NOT_REQUIRED
    postcondition_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in ("capability_id", "input_schema_id", "output_schema_id"):
            object.__setattr__(
                self, field_name, require_identifier(getattr(self, field_name), field_name)
            )
        for field_name in ("display_name", "description"):
            object.__setattr__(self, field_name, require_text(getattr(self, field_name), field_name))
        object.__setattr__(
            self,
            "postcondition_ids",
            normalize_unique(self.postcondition_ids, "postcondition_ids"),
        )
        self._validate_policy()

    def _validate_policy(self) -> None:
        if self.kind is CapabilityKind.OBSERVATION:
            if self.required_authority is not ApplicationAuthority.OBSERVE:
                raise ValueError("observation capabilities require observe authority")
            if self.reversibility is not Reversibility.NOT_APPLICABLE:
                raise ValueError("observation reversibility must be not_applicable")
            if self.confirmation is not ConfirmationPolicy.NOT_REQUIRED:
                raise ValueError("observation confirmation must be not_required")
            if self.postcondition_ids:
                raise ValueError("observation capabilities cannot declare postconditions")
            return
        if self.required_authority is ApplicationAuthority.OBSERVE:
            raise ValueError("action capabilities require propose, modify, or execute authority")
        if self.reversibility is Reversibility.NOT_APPLICABLE:
            raise ValueError("action capabilities must declare reversibility")
        if not self.postcondition_ids:
            raise ValueError("action capabilities require deterministic postconditions")
        if (
            self.reversibility is Reversibility.IRREVERSIBLE
            and self.confirmation is not ConfirmationPolicy.ALWAYS
        ):
            raise ValueError("irreversible actions always require confirmation")


@dataclass(frozen=True, slots=True)
class CapabilityRegistryEntry:
    entry_id: str
    connector_id: str
    instance_id: str
    application_id: str
    capability: CapabilityDescriptor
    resource_scopes: tuple[str, ...] = ()
    available: bool = True

    def __post_init__(self) -> None:
        for field_name in ("entry_id", "connector_id", "instance_id", "application_id"):
            object.__setattr__(
                self, field_name, require_identifier(getattr(self, field_name), field_name)
            )
        object.__setattr__(
            self,
            "resource_scopes",
            normalize_unique(self.resource_scopes, "resource_scopes"),
        )

    @property
    def capability_id(self) -> str:
        return self.capability.capability_id
