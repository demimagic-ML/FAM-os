"""Application Fabric declarations for deterministic Linux capability adapters."""

from dataclasses import dataclass
from datetime import datetime

from fam_os.applications import (
    ApplicationAuthority, ApplicationIdentity, ApplicationInstance,
    CapabilityDescriptor, CapabilityKind, CapabilityRegistryEntry,
    ConfirmationPolicy, ConnectorRegistration, ConnectorTransportKind,
    Reversibility,
)


@dataclass(frozen=True, slots=True)
class DeterministicCapabilityDeclaration:
    capability: CapabilityDescriptor
    resource_scopes: tuple[str, ...] = ()


def file_observation(scopes):
    return DeterministicCapabilityDeclaration(CapabilityDescriptor(
        "linux.file.observe", "Observe scoped file",
        "Read bounded metadata, hash, and optionally content from an approved file.",
        CapabilityKind.OBSERVATION, ApplicationAuthority.OBSERVE,
        "linux.file.observe.input.v1", "linux.file.observe.output.v1",
    ), tuple(scopes))


def file_write(scopes):
    return DeterministicCapabilityDeclaration(CapabilityDescriptor(
        "linux.file.atomic_write", "Replace scoped file atomically",
        "Apply an approved content- and revision-bound atomic file replacement.",
        CapabilityKind.ACTION, ApplicationAuthority.MODIFY,
        "linux.file.atomic_write.input.v1", "linux.file.atomic_write.output.v1",
        Reversibility.IRREVERSIBLE, ConfirmationPolicy.ALWAYS, ("file.sha256",),
    ), tuple(scopes))


def mime_observation(scopes):
    return DeterministicCapabilityDeclaration(CapabilityDescriptor(
        "linux.mime.observe", "Identify scoped file MIME type",
        "Identify a file through bounded magic data with extension fallback.",
        CapabilityKind.OBSERVATION, ApplicationAuthority.OBSERVE,
        "linux.mime.observe.input.v1", "linux.mime.observe.output.v1",
    ), tuple(scopes))


def portal_open_uri(schemes):
    return DeterministicCapabilityDeclaration(CapabilityDescriptor(
        "linux.portal.open_uri", "Open URI through desktop portal",
        "Request the desktop portal to open an approved URI after confirmation.",
        CapabilityKind.ACTION, ApplicationAuthority.EXECUTE,
        "linux.portal.open_uri.input.v1", "linux.portal.open_uri.output.v1",
        Reversibility.IRREVERSIBLE, ConfirmationPolicy.ALWAYS,
        ("portal.request.accepted",),
    ), tuple(f"scheme:{item}" for item in schemes))


def build_deterministic_registration(
    connector_id: str, instance_id: str,
    declarations: tuple[DeterministicCapabilityDeclaration, ...],
    connected_at: datetime,
):
    application = ApplicationIdentity(
        "fam.linux.deterministic", "FAM Linux deterministic capabilities"
    )
    instance = ApplicationInstance(instance_id, application, connector_id)
    entries = tuple(
        CapabilityRegistryEntry(
            f"{instance_id}:{item.capability.capability_id}", connector_id,
            instance_id, application.application_id, item.capability,
            item.resource_scopes,
        )
        for item in declarations
    )
    return ConnectorRegistration(
        connector_id, ConnectorTransportKind.OS_TOOL,
        "fam.linux.deterministic", "1", instance, entries, connected_at,
    )
