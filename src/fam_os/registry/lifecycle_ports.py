"""Replaceable persistence and immutable-artifact ports for package lifecycle."""

from __future__ import annotations

from typing import Protocol

from fam_os.experts.registry_contracts import ExpertPackageCoordinate
from fam_os.registry.lifecycle_contracts import ExpertPackageInstallationState
from fam_os.registry.package import ArtifactDigest


class PackageLifecycleStateStore(Protocol):
    def load(self) -> ExpertPackageInstallationState: ...

    def commit(
        self,
        expected_revision: int,
        state: ExpertPackageInstallationState,
    ) -> None: ...


class InstalledPackageArtifactStore(Protocol):
    def install(
        self,
        coordinate: ExpertPackageCoordinate,
        source_locator: str,
        expected_digest: ArtifactDigest,
    ) -> str: ...

    def verify(self, artifact_locator: str, expected_digest: ArtifactDigest) -> None: ...

    def remove(self, artifact_locator: str) -> None: ...
