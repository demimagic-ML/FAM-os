import hashlib
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from fam_os.product.atomic_update import AtomicReleaseManager
from fam_os.product.update_contracts import ComponentKind, ReleaseComponent
from fam_os.product.update_signing import sign_manifest


class AtomicReleaseUpdateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.key = Ed25519PrivateKey.generate()
        self.manager = AtomicReleaseManager(
            self.root / "runtime", {"release-key": self.key.public_key()},
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _manifest(self, release_id: str):
        components = []
        for kind in ComponentKind:
            source = self.root / f"{release_id}-{kind.value}"
            source.write_text(f"{release_id}:{kind.value}")
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            components.append(ReleaseComponent(kind, "payload", str(source), digest))
        return sign_manifest(release_id, tuple(components), "release-key", self.key)

    def test_activates_all_component_kinds_as_one_release(self) -> None:
        receipt = self.manager.apply(self._manifest("v1"), lambda path: True)
        self.assertTrue(receipt.activated)
        self.assertEqual(self.manager.active_release_id(), "v1")
        active = self.root / "runtime" / "active"
        self.assertEqual({path.parent.name for path in active.rglob("payload")},
                         {kind.value for kind in ComponentKind})

    def test_failed_health_check_leaves_previous_release_active(self) -> None:
        self.manager.apply(self._manifest("v1"), lambda path: True)
        receipt = self.manager.apply(self._manifest("v2"), lambda path: False)
        self.assertFalse(receipt.activated)
        self.assertEqual(receipt.active_release_id, "v1")
        self.assertEqual(self.manager.active_release_id(), "v1")

    def test_rollback_switches_complete_release(self) -> None:
        self.manager.apply(self._manifest("v1"), lambda path: True)
        self.manager.apply(self._manifest("v2"), lambda path: True)
        receipt = self.manager.rollback("v1", lambda path: True)
        self.assertTrue(receipt.rolled_back)
        self.assertEqual(self.manager.active_release_id(), "v1")

    def test_tampered_component_is_rejected_without_activation(self) -> None:
        manifest = self._manifest("v1")
        Path(manifest.components[0].source_path).write_text("tampered")
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            self.manager.apply(manifest, lambda path: True)
        self.assertIsNone(self.manager.active_release_id())


if __name__ == "__main__":
    unittest.main()
