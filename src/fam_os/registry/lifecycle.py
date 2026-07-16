"""Transactional expert-package install, update, disable, rollback, and removal."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
import hashlib
from typing import Callable
from uuid import uuid4

from fam_os.experts.compatibility_contracts import (
    ExpertCompatibilityReport,
    ExpertCompatibilityStatus,
)
from fam_os.experts.manifest import ExpertManifest
from fam_os.experts.registry_contracts import ExpertPackageCoordinate, coordinate_for
from fam_os.registry.lifecycle_contracts import (
    ExpertPackageInstallationState,
    InstalledExpertPackage,
    PackageLifecycleAction,
    PackageLifecycleEvent,
    PendingArtifactRemoval,
)
from fam_os.registry.lifecycle_ports import InstalledPackageArtifactStore, PackageLifecycleStateStore
from fam_os.registry.trust_contracts import PackageValidationReport
from fam_os.registry.package import ArtifactDigest
from fam_os.registry.signing_payload import expert_package_signing_payload


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class ExpertPackageLifecycle:
    state_store: PackageLifecycleStateStore
    artifact_store: InstalledPackageArtifactStore
    clock: Callable[[], datetime] = _now
    event_id_factory: Callable[[], str] = lambda: str(uuid4())

    def install(
        self,
        manifest: ExpertManifest,
        source_locator: str,
        validation: PackageValidationReport,
        compatibility: ExpertCompatibilityReport,
    ) -> ExpertPackageInstallationState:
        state = self.state_store.load()
        coordinate = self._admit(manifest, validation, compatibility)
        existing = _find(state, coordinate)
        if existing is not None:
            _require_idempotent_match(existing, manifest, validation)
            self.artifact_store.verify(existing.artifact_locator, existing.artifact_digest)
            return state
        if any(item.expert_id == manifest.expert_id for item in state.packages):
            raise ValueError("use update to install another version of an existing expert")
        locator = self.artifact_store.install(
            coordinate, source_locator, validation.observed_artifact_digest
        )
        enabled = _can_activate(compatibility.status)
        package = _installed(manifest, locator, validation, compatibility, self.clock(), enabled)
        return self._commit(
            state, (*state.packages, package), PackageLifecycleAction.INSTALL,
            coordinate, manifest.expert_id,
        )

    def update(
        self,
        manifest: ExpertManifest,
        source_locator: str,
        validation: PackageValidationReport,
        compatibility: ExpertCompatibilityReport,
    ) -> ExpertPackageInstallationState:
        state = self.state_store.load()
        coordinate = self._admit(manifest, validation, compatibility)
        existing = _find(state, coordinate)
        if existing is not None:
            _require_idempotent_match(existing, manifest, validation)
            self.artifact_store.verify(existing.artifact_locator, existing.artifact_digest)
            return state
        versions = tuple(item for item in state.packages if item.expert_id == manifest.expert_id)
        if not versions:
            raise ValueError("update requires an installed version of the same expert")
        locator = self.artifact_store.install(
            coordinate, source_locator, validation.observed_artifact_digest
        )
        activate = _can_activate(compatibility.status)
        retained = tuple(
            replace(item, enabled=False) if activate and item.expert_id == manifest.expert_id else item
            for item in state.packages
        )
        package = _installed(manifest, locator, validation, compatibility, self.clock(), activate)
        return self._commit(
            state, (*retained, package), PackageLifecycleAction.UPDATE,
            coordinate, manifest.expert_id,
        )

    def disable(self, coordinate: ExpertPackageCoordinate) -> ExpertPackageInstallationState:
        state = self.state_store.load()
        package = _require_installed(state, coordinate)
        if not package.enabled:
            return state
        packages = tuple(replace(item, enabled=False) if item.coordinate == coordinate else item for item in state.packages)
        return self._commit(
            state, packages, PackageLifecycleAction.DISABLE, coordinate, package.expert_id
        )

    def rollback(self, coordinate: ExpertPackageCoordinate) -> ExpertPackageInstallationState:
        state = self.state_store.load()
        target = _require_installed(state, coordinate)
        if not _can_activate(target.compatibility_status):
            raise ValueError("rollback target is not currently activatable")
        self.artifact_store.verify(target.artifact_locator, target.artifact_digest)
        if target.enabled:
            return state
        packages = tuple(
            replace(item, enabled=item.coordinate == coordinate)
            if item.expert_id == target.expert_id else item
            for item in state.packages
        )
        return self._commit(
            state, packages, PackageLifecycleAction.ROLLBACK, coordinate, target.expert_id
        )

    def remove(self, coordinate: ExpertPackageCoordinate) -> ExpertPackageInstallationState:
        state = self.state_store.load()
        package = _require_installed(state, coordinate)
        if package.enabled:
            raise ValueError("disable or rollback before removing an active package")
        packages = tuple(item for item in state.packages if item.coordinate != coordinate)
        pending = (*state.pending_artifact_removals, PendingArtifactRemoval(
            coordinate, package.artifact_locator
        ))
        committed = self._commit(
            state, packages, PackageLifecycleAction.REMOVE, coordinate, package.expert_id,
            pending=pending,
        )
        return self._recover_one(committed, pending[-1])

    def recover(self) -> ExpertPackageInstallationState:
        state = self.state_store.load()
        for pending in tuple(state.pending_artifact_removals):
            state = self._recover_one(state, pending)
        return state

    def _admit(self, manifest, validation, compatibility) -> ExpertPackageCoordinate:
        coordinate = coordinate_for(manifest)
        expected = (coordinate.package_id, coordinate.package_version)
        if expected != (validation.package_id, validation.package_version) or not validation.accepted:
            raise ValueError("accepted package validation must match the manifest coordinate")
        if expected != (compatibility.package_id, compatibility.package_version):
            raise ValueError("compatibility evidence must match the manifest coordinate")
        if manifest.expert_id != compatibility.expert_id:
            raise ValueError("compatibility evidence must match the manifest expert")
        if compatibility.status is ExpertCompatibilityStatus.INCOMPATIBLE:
            raise ValueError("incompatible package cannot be installed")
        return coordinate

    def _commit(self, state, packages, action, coordinate, expert_id, *, pending=None):
        previous = _active_for_expert(state.packages, expert_id)
        ordered = tuple(sorted(packages, key=lambda item: item.coordinate))
        active_after = _active_for_expert(ordered, expert_id)
        event = PackageLifecycleEvent(
            self.event_id_factory(), state.revision + 1, self.clock(), action,
            coordinate, previous, active_after, "committed",
        )
        removals = state.pending_artifact_removals if pending is None else tuple(pending)
        updated = ExpertPackageInstallationState(
            state.revision + 1, ordered, removals, (*state.events, event)
        )
        self.state_store.commit(state.revision, updated)
        return updated

    def _recover_one(self, state, pending):
        self.artifact_store.remove(pending.artifact_locator)
        remaining = tuple(
            item for item in state.pending_artifact_removals if item != pending
        )
        event = PackageLifecycleEvent(
            self.event_id_factory(), state.revision + 1, self.clock(),
            PackageLifecycleAction.CLEANUP, pending.coordinate, None, None,
            "artifact_removed",
        )
        updated = ExpertPackageInstallationState(
            state.revision + 1, state.packages, remaining, (*state.events, event)
        )
        self.state_store.commit(state.revision, updated)
        return updated


def _installed(manifest, locator, validation, compatibility, installed_at, enabled):
    return InstalledExpertPackage(
        coordinate_for(manifest), manifest.expert_id, locator,
        validation.observed_artifact_digest, _manifest_digest(manifest),
        validation.effective_trust,
        validation.policy_id, compatibility.status, compatibility.validation_profile_id,
        installed_at, enabled,
    )


def _find(state, coordinate):
    return next((item for item in state.packages if item.coordinate == coordinate), None)


def _require_installed(state, coordinate):
    package = _find(state, coordinate)
    if package is None:
        raise KeyError("expert package coordinate is not installed")
    return package


def _can_activate(status):
    return status in (ExpertCompatibilityStatus.COMPATIBLE, ExpertCompatibilityStatus.COMPATIBLE_CPU_ONLY)


def _manifest_digest(manifest):
    value = hashlib.sha256(expert_package_signing_payload(manifest)).hexdigest()
    return ArtifactDigest("sha256", value)


def _require_idempotent_match(existing, manifest, validation):
    if (
        existing.expert_id != manifest.expert_id
        or existing.artifact_digest != validation.observed_artifact_digest
        or existing.manifest_digest != _manifest_digest(manifest)
    ):
        raise ValueError("installed package coordinate does not match idempotent content")


def _active_for_expert(packages, expert_id):
    return next((item.coordinate for item in packages if item.expert_id == expert_id and item.enabled), None)
