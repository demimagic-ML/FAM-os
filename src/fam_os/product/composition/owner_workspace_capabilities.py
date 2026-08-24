"""Application descriptors for bounded owner-workspace intelligence."""

from fam_os.applications import (
    ApplicationAuthority,
    CapabilityDescriptor,
    CapabilityKind,
    ConfirmationPolicy,
    Reversibility,
    WORKSPACE_MAP_CAPABILITY,
    WORKSPACE_PATCH_CAPABILITY,
    WORKSPACE_RESTORE_CAPABILITY,
    WORKSPACE_RETRIEVE_CAPABILITY,
)


def workspace_descriptors() -> tuple[CapabilityDescriptor, ...]:
    return (
        CapabilityDescriptor(
            WORKSPACE_MAP_CAPABILITY,
            "Map workspace",
            "Recursively discover a bounded, symlink-safe workspace file map.",
            CapabilityKind.OBSERVATION,
            ApplicationAuthority.OBSERVE,
            "fam.os.workspace-map.input.v1",
            "fam.os.workspace-map.output.v1",
        ),
        CapabilityDescriptor(
            WORKSPACE_RETRIEVE_CAPABILITY,
            "Retrieve relevant workspace files",
            "Read a bounded deterministic selection of relevant UTF-8 files.",
            CapabilityKind.OBSERVATION,
            ApplicationAuthority.OBSERVE,
            "fam.os.workspace-retrieve.input.v1",
            "fam.os.workspace-retrieve.output.v1",
        ),
        CapabilityDescriptor(
            WORKSPACE_PATCH_CAPABILITY,
            "Apply workspace patch",
            "Preview and modify up to four already-observed UTF-8 workspace files.",
            CapabilityKind.ACTION,
            ApplicationAuthority.MODIFY,
            "fam.os.workspace-patch.input.v1",
            "fam.os.workspace-patch.output.v1",
            Reversibility.REVERSIBLE,
            ConfirmationPolicy.ALWAYS,
            ("workspace.files-match-proposal",),
        ),
        CapabilityDescriptor(
            WORKSPACE_RESTORE_CAPABILITY,
            "Restore workspace patch",
            "Restore the exact prior bytes while the approved patch is unchanged.",
            CapabilityKind.ACTION,
            ApplicationAuthority.MODIFY,
            "fam.os.workspace-restore.input.v1",
            "fam.os.workspace-restore.output.v1",
            Reversibility.IRREVERSIBLE,
            ConfirmationPolicy.ALWAYS,
            ("workspace.files-restored",),
        ),
    )
