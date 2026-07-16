"""Application Fabric declarations for the Linux accessibility bridge."""

from datetime import datetime

from fam_os.applications import (
    ApplicationAuthority,
    ApplicationIdentity,
    ApplicationInstance,
    CapabilityDescriptor,
    CapabilityKind,
    CapabilityRegistryEntry,
    ConfirmationPolicy,
    ConnectorRegistration,
    ConnectorTransportKind,
    Reversibility,
)


def accessibility_observation() -> CapabilityDescriptor:
    return CapabilityDescriptor(
        "linux.accessibility.observe_tree",
        "Observe application accessibility tree",
        "Read a permission-filtered and bounded semantic accessibility tree.",
        CapabilityKind.OBSERVATION,
        ApplicationAuthority.OBSERVE,
        "linux.accessibility.observe_tree.input.v1",
        "linux.accessibility.observe_tree.output.v1",
    )


def accessibility_action() -> CapabilityDescriptor:
    return CapabilityDescriptor(
        "linux.accessibility.invoke_action",
        "Invoke accessibility action",
        "Invoke an approved allowlisted action after revalidating object identity.",
        CapabilityKind.ACTION,
        ApplicationAuthority.EXECUTE,
        "linux.accessibility.invoke_action.input.v1",
        "linux.accessibility.invoke_action.output.v1",
        Reversibility.IRREVERSIBLE,
        ConfirmationPolicy.ALWAYS,
        ("accessibility.action.poststate",),
    )


def build_accessibility_registration(
    connector_id: str,
    instance_id: str,
    process_id: int,
    connected_at: datetime,
) -> ConnectorRegistration:
    application = ApplicationIdentity(
        "fam.linux.accessibility", "FAM Linux accessibility bridge"
    )
    instance = ApplicationInstance(
        instance_id, application, connector_id, process_id=process_id
    )
    capabilities = (accessibility_observation(), accessibility_action())
    entries = tuple(
        CapabilityRegistryEntry(
            f"{instance_id}:{capability.capability_id}",
            connector_id,
            instance_id,
            application.application_id,
            capability,
            (f"process:{process_id}",),
        )
        for capability in capabilities
    )
    return ConnectorRegistration(
        connector_id,
        ConnectorTransportKind.ACCESSIBILITY,
        "at-spi2",
        "2.0",
        instance,
        entries,
        connected_at,
    )
