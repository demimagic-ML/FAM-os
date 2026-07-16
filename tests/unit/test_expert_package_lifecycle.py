import hashlib
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from fam_os.adapters.filesystem import (
    ImmutablePackageArtifactStore,
    JsonPackageLifecycleStateStore,
)
from fam_os.experts import ExpertCompatibilityReport, ExpertCompatibilityStatus
from fam_os.experts.registry_contracts import ExpertPackageCoordinate
from fam_os.registry import (
    ArtifactDigest,
    PackageTrustLevel,
    PackageValidationReport,
)
from fam_os.registry.lifecycle import ExpertPackageLifecycle
from tests.unit.test_package_expert_manifests import _manifest, _package


NOW = datetime(2026, 7, 16, 21, 0, tzinfo=timezone.utc)
ARTIFACT = b"immutable expert package"
DIGEST = ArtifactDigest("sha256", hashlib.sha256(ARTIFACT).hexdigest())


class ExpertPackageLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.source = self.root / "source.bin"
        self.source.write_bytes(ARTIFACT)
        self.state_store = JsonPackageLifecycleStateStore(self.root / "state.json")
        self.artifact_store = ImmutablePackageArtifactStore(self.root / "packages")
        ids = iter(range(30))
        self.lifecycle = ExpertPackageLifecycle(
            self.state_store,
            self.artifact_store,
            clock=lambda: NOW,
            event_id_factory=lambda: f"lifecycle-{next(ids)}",
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_install_update_rollback_disable_and_remove_survive_restart(self) -> None:
        first = self.manifest("1.0.0")
        installed = self.lifecycle.install(
            first, str(self.source), self.validation(first), self.compatibility(first)
        )
        self.assertTrue(installed.packages[0].enabled)

        second = self.manifest("2.0.0")
        updated = self.lifecycle.update(
            second, str(self.source), self.validation(second), self.compatibility(second)
        )
        self.assertEqual("2.0.0", self.active(updated).package_version)
        self.assertEqual(2, len(updated.packages))

        restarted = ExpertPackageLifecycle(self.state_store, self.artifact_store)
        rolled_back = restarted.rollback(self.coordinate(first))
        self.assertEqual("1.0.0", self.active(rolled_back).package_version)
        disabled = restarted.disable(self.coordinate(second))
        self.assertEqual(rolled_back, disabled)
        removed = restarted.remove(self.coordinate(second))
        self.assertEqual((self.coordinate(first),), tuple(item.coordinate for item in removed.packages))
        self.assertEqual((), removed.pending_artifact_removals)
        self.assertEqual("cleanup", removed.events[-1].action.value)

    def test_constrained_update_is_retained_but_cannot_displace_known_good(self) -> None:
        first = self.manifest("1.0.0")
        state = self.lifecycle.install(
            first, str(self.source), self.validation(first), self.compatibility(first)
        )
        second = self.manifest("2.0.0")
        constrained = self.compatibility(
            second, ExpertCompatibilityStatus.CURRENTLY_CONSTRAINED
        )
        state = self.lifecycle.update(second, str(self.source), self.validation(second), constrained)
        self.assertEqual(self.coordinate(first), self.active(state))
        self.assertFalse(next(item for item in state.packages if item.coordinate == self.coordinate(second)).enabled)
        with self.assertRaisesRegex(ValueError, "not currently activatable"):
            self.lifecycle.rollback(self.coordinate(second))

    def test_rejects_untrusted_mismatched_and_incompatible_evidence_before_copy(self) -> None:
        manifest = self.manifest("1.0.0")
        rejected = replace(
            self.validation(manifest),
            accepted=False,
            reason_code="denied",
            effective_trust=None,
            verified_key_id=None,
        )
        with self.assertRaisesRegex(ValueError, "accepted"):
            self.lifecycle.install(manifest, str(self.source), rejected, self.compatibility(manifest))
        incompatible = self.compatibility(manifest, ExpertCompatibilityStatus.INCOMPATIBLE)
        with self.assertRaisesRegex(ValueError, "incompatible"):
            self.lifecycle.install(manifest, str(self.source), self.validation(manifest), incompatible)
        self.assertEqual((), self.state_store.load().packages)

    def test_digest_failure_and_symlink_source_leave_state_unchanged(self) -> None:
        manifest = self.manifest("1.0.0")
        self.source.write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "digest"):
            self.lifecycle.install(
                manifest, str(self.source), self.validation(manifest), self.compatibility(manifest)
            )
        self.source.unlink()
        real = self.root / "real.bin"
        real.write_bytes(ARTIFACT)
        self.source.symlink_to(real)
        with self.assertRaises(OSError):
            self.lifecycle.install(
                manifest, str(self.source), self.validation(manifest), self.compatibility(manifest)
            )
        self.assertEqual(0, self.state_store.load().revision)

    def test_same_coordinate_with_changed_manifest_is_not_treated_as_idempotent(self) -> None:
        manifest = self.manifest("1.0.0")
        self.lifecycle.install(
            manifest, str(self.source), self.validation(manifest), self.compatibility(manifest)
        )
        changed = replace(manifest, display_name="Changed without a new version")
        with self.assertRaisesRegex(ValueError, "idempotent content"):
            self.lifecycle.install(
                changed,
                str(self.source),
                self.validation(changed),
                self.compatibility(changed),
            )

    def test_rollback_rechecks_retained_artifact_integrity(self) -> None:
        first = self.manifest("1.0.0")
        second = self.manifest("2.0.0")
        state = self.lifecycle.install(
            first, str(self.source), self.validation(first), self.compatibility(first)
        )
        state = self.lifecycle.update(
            second, str(self.source), self.validation(second), self.compatibility(second)
        )
        retained = next(item for item in state.packages if item.coordinate == self.coordinate(first))
        path = self.root / "packages" / retained.artifact_locator
        path.chmod(0o600)
        path.write_bytes(b"tampered retained version")
        with self.assertRaisesRegex(ValueError, "unexpected content"):
            self.lifecycle.rollback(self.coordinate(first))

    def test_failed_artifact_cleanup_is_durably_recoverable(self) -> None:
        manifest = self.manifest("1.0.0")
        self.lifecycle.install(
            manifest, str(self.source), self.validation(manifest), self.compatibility(manifest)
        )
        self.lifecycle.disable(self.coordinate(manifest))
        original = self.artifact_store.remove
        self.artifact_store.remove = lambda _: (_ for _ in ()).throw(OSError("busy"))
        with self.assertRaisesRegex(OSError, "busy"):
            self.lifecycle.remove(self.coordinate(manifest))
        pending = self.state_store.load()
        self.assertEqual((), pending.packages)
        self.assertEqual(1, len(pending.pending_artifact_removals))
        self.artifact_store.remove = original
        recovered = self.lifecycle.recover()
        self.assertEqual((), recovered.pending_artifact_removals)

    def manifest(self, version):
        return _manifest(package=_package(
            package_version=version,
            artifact_digest=DIGEST,
        ))

    def validation(self, manifest):
        return PackageValidationReport(
            manifest.package.package_id,
            manifest.package.package_version,
            True,
            "accepted",
            PackageTrustLevel.SIGNED,
            DIGEST,
            "policy-1",
            "fam-release-key-1",
        )

    def compatibility(self, manifest, status=ExpertCompatibilityStatus.COMPATIBLE):
        reasons = () if status is ExpertCompatibilityStatus.COMPATIBLE else ("current.busy",)
        return ExpertCompatibilityReport(
            manifest.package.package_id,
            manifest.package.package_version,
            manifest.expert_id,
            "inventory-1",
            "budget-1",
            "full-reference-workstation",
            status,
            8 * 1024**3,
            32 * 1024**3,
            ("nvme-root",),
            ("gpu-0",),
            reasons,
        )

    @staticmethod
    def coordinate(manifest):
        return ExpertPackageCoordinate(
            manifest.package.package_id, manifest.package.package_version
        )

    @staticmethod
    def active(state):
        return next(item.coordinate for item in state.packages if item.enabled)


if __name__ == "__main__":
    unittest.main()
