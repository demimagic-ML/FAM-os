"""Exact capability candidates joined across discovery, lifecycle, and bindings."""

from __future__ import annotations

from dataclasses import dataclass

from fam_os.experts.contracts import ExpertTier
from fam_os.experts.manifest import ExpertManifest
from fam_os.experts.registry import LocalExpertRegistry
from fam_os.experts.registry_contracts import coordinate_for
from fam_os.experts.runtime_binding import ExpertRuntimeBinding, validate_runtime_binding
from fam_os.registry.lifecycle_contracts import (
    ExpertPackageInstallationState,
    InstalledExpertPackage,
)


@dataclass(frozen=True, slots=True)
class InstalledExpertCandidate:
    manifest: ExpertManifest
    installation: InstalledExpertPackage
    runtime_binding: ExpertRuntimeBinding


@dataclass(frozen=True, slots=True)
class InstalledExpertCandidateResolver:
    registry: LocalExpertRegistry
    bindings: tuple[ExpertRuntimeBinding, ...]

    def resolve(
        self,
        capability_id: str,
        state: ExpertPackageInstallationState,
        tier: ExpertTier | None = None,
    ) -> tuple[InstalledExpertCandidate, ...]:
        installations = {item.coordinate: item for item in state.packages if item.enabled}
        bindings = {item.coordinate: item for item in self.bindings}
        if len(bindings) != len(self.bindings):
            raise ValueError("runtime bindings must have unique package coordinates")
        candidates = []
        for manifest in self.registry.find_by_capability(capability_id, tier):
            coordinate = coordinate_for(manifest)
            if coordinate not in installations or coordinate not in bindings:
                continue
            binding = bindings[coordinate]
            validate_runtime_binding(manifest, binding)
            candidates.append(InstalledExpertCandidate(
                manifest, installations[coordinate], binding
            ))
        return tuple(candidates)
