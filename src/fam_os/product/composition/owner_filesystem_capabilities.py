"""Capability descriptors for the owner filesystem connector."""

from fam_os.applications import (
    ApplicationAuthority,
    CapabilityDescriptor,
    CapabilityKind,
    ConfirmationPolicy,
    Reversibility,
)


def filesystem_descriptors() -> tuple[CapabilityDescriptor, ...]:
    return (
        CapabilityDescriptor(
            "os.directory.inspect", "Inspect directory",
            "Inspect a scoped local directory.",
            CapabilityKind.OBSERVATION, ApplicationAuthority.OBSERVE,
            "fam.os.directory-inspect.input.v1",
            "fam.os.directory-inspect.output.v1",
        ),
        CapabilityDescriptor(
            "os.directory.list", "List directory",
            "List bounded entries in a local directory.",
            CapabilityKind.OBSERVATION, ApplicationAuthority.OBSERVE,
            "fam.os.directory-list.input.v1",
            "fam.os.directory-list.output.v1",
        ),
        CapabilityDescriptor(
            "os.file.read", "Read file",
            "Read bounded text bytes from a local file.",
            CapabilityKind.OBSERVATION, ApplicationAuthority.OBSERVE,
            "fam.os.file-read.input.v1", "fam.os.file-read.output.v1",
        ),
        CapabilityDescriptor(
            "os.directory.create", "Create directory",
            "Create one empty scoped directory.",
            CapabilityKind.ACTION, ApplicationAuthority.MODIFY,
            "fam.os.directory-create.input.v1",
            "fam.os.directory-create.output.v1",
            Reversibility.REVERSIBLE, ConfirmationPolicy.ALWAYS,
            ("directory.exists-empty",),
        ),
        CapabilityDescriptor(
            "os.directory.remove-empty", "Remove created empty directory",
            "Reverse a create operation only while the exact directory remains empty.",
            CapabilityKind.ACTION, ApplicationAuthority.MODIFY,
            "fam.os.directory-remove-empty.input.v1",
            "fam.os.directory-remove-empty.output.v1",
            Reversibility.IRREVERSIBLE, ConfirmationPolicy.ALWAYS,
            ("directory.absent",),
        ),
    )
