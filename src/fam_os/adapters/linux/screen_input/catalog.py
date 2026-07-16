"""Application Fabric declarations for the restricted desktop fallback."""

from datetime import datetime

from fam_os.applications import (
    ApplicationAuthority, ApplicationIdentity, ApplicationInstance,
    CapabilityDescriptor, CapabilityKind, CapabilityRegistryEntry,
    ConfirmationPolicy, ConnectorRegistration, ConnectorTransportKind, Reversibility,
)


def screen_observation() -> CapabilityDescriptor:
    return CapabilityDescriptor(
        "linux.screen.observe_active_window", "Observe active application pixels",
        "Capture a bounded PNG of one exact active application window.",
        CapabilityKind.OBSERVATION, ApplicationAuthority.OBSERVE,
        "linux.screen.observe_active_window.input.v1",
        "linux.screen.observe_active_window.output.v1",
    )


def controlled_input() -> CapabilityDescriptor:
    return CapabilityDescriptor(
        "linux.input.control_active_window", "Control active application input",
        "Invoke one allowlisted input primitive against an exact unchanged scene.",
        CapabilityKind.ACTION, ApplicationAuthority.EXECUTE,
        "linux.input.control_active_window.input.v1",
        "linux.input.control_active_window.output.v1",
        Reversibility.IRREVERSIBLE, ConfirmationPolicy.ALWAYS,
        ("screen.input.postframe",),
    )


def build_screen_input_registration(
    connector_id: str, instance_id: str, application_id: str,
    process_id: int, window_id: str, connected_at: datetime,
) -> ConnectorRegistration:
    application = ApplicationIdentity(application_id, "Screen/input fallback")
    instance = ApplicationInstance(
        instance_id, application, connector_id, process_id=process_id,
    )
    entries = tuple(
        CapabilityRegistryEntry(
            f"{instance_id}:{capability.capability_id}", connector_id, instance_id,
            application_id, capability, (f"process:{process_id}", f"window:{window_id}"),
        )
        for capability in (screen_observation(), controlled_input())
    )
    return ConnectorRegistration(
        connector_id, ConnectorTransportKind.SCREEN_INPUT,
        "x11-pillow-xtest", "1.0", instance, entries, connected_at,
    )
