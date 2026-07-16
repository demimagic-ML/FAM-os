"""Application and running-instance identity contracts."""

from __future__ import annotations

from dataclasses import dataclass

from fam_os.applications.identifiers import (
    normalize_unique,
    require_identifier,
    require_text,
)


@dataclass(frozen=True, slots=True)
class ApplicationIdentity:
    application_id: str
    display_name: str
    vendor: str | None = None
    version: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "application_id", require_identifier(self.application_id, "application_id")
        )
        object.__setattr__(self, "display_name", require_text(self.display_name, "display_name"))
        for field_name in ("vendor", "version"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, require_text(value, field_name))


@dataclass(frozen=True, slots=True)
class ApplicationInstance:
    instance_id: str
    application: ApplicationIdentity
    connector_id: str
    process_id: int | None = None
    workspace_uris: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "instance_id", require_identifier(self.instance_id, "instance_id"))
        object.__setattr__(
            self, "connector_id", require_identifier(self.connector_id, "connector_id")
        )
        if self.process_id is not None and self.process_id <= 0:
            raise ValueError("process_id must be positive")
        object.__setattr__(
            self,
            "workspace_uris",
            normalize_unique(self.workspace_uris, "workspace_uris"),
        )
