"""Explicit expert-manifest version migrations."""

from __future__ import annotations

from fam_os.experts.legacy_manifest import ExpertManifestV1Alpha1
from fam_os.experts.manifest import ExpertManifest


def migrate_expert_manifest_v1alpha1(value: ExpertManifestV1Alpha1) -> ExpertManifest:
    """Upgrade one legacy manifest, rejecting noncanonical capability claims."""

    return ExpertManifest(
        package=value.package,
        expert_id=value.expert_id,
        display_name=value.display_name,
        tier=value.tier,
        capabilities=value.capabilities,
        runtime_contract_id=value.runtime_contract_id,
        artifact_ids=value.artifact_ids,
        resources=value.resources,
        required_verifier_ids=value.required_verifier_ids,
    )
