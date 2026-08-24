import tempfile
import tarfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from fam_os.product.atomic_update import AtomicReleaseManager
from fam_os.product.release_bundle import (
    ReleaseBundleBuilder,
    ReleaseBundleInput,
    load_release_bundle,
)
from fam_os.product.release_assembly import CompleteReleaseAssembler
from fam_os.product.update_contracts import ComponentKind
from fam_os.core.engineering import SignedToolRecipe, ToolchainMountSourceKind
from fam_os.schemas import loads_document


class CompleteReleaseBundleTests(unittest.TestCase):
    def test_repository_assembly_is_complete_and_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            wheelhouse = root / "wheelhouse"
            wheelhouse.mkdir()
            wheel = wheelhouse / "fam_os-0.1.0-py3-none-any.whl"
            wheel.write_bytes(b"wheel")
            key = Ed25519PrivateKey.generate()
            repository = Path(__file__).parents[2]
            first = CompleteReleaseAssembler(repository).build(
                "v1", wheelhouse, root / "bundle-1", "key", key,
            )
            second = CompleteReleaseAssembler(repository).build(
                "v1", wheelhouse, root / "bundle-2", "key", key,
            )
            self.assertEqual(first, second)
            self.assertEqual(set(ComponentKind), {item.kind for item in first.components})
            names = {item.kind: item.name for item in first.components}
            self.assertEqual("systemd.tar", names[ComponentKind.SERVICE_UNIT])
            self.assertEqual("migrations.tar", names[ComponentKind.MIGRATION])
            with tarfile.open(
                root / "bundle-1/components/service_unit/systemd.tar",
            ) as archive:
                self.assertIn("fam-os-userns", archive.getnames())
            with tarfile.open(
                root / "bundle-1/components/expert/experts.tar",
            ) as archive:
                self.assertIn(
                    "documentation-recipes/api_reference.json",
                    archive.getnames(),
                )
                self.assertIn(
                    "review-recipes/independent.json", archive.getnames(),
                )
                preview = archive.extractfile(
                    "integration-recipes/python-static-http.json"
                )
                self.assertIsNotNone(preview)
                preview_recipe = loads_document(
                    preview.read().decode("utf-8")
                )
                self.assertEqual(
                    "integration.python.static-http",
                    preview_recipe.recipe_id,
                )
                root_api = archive.extractfile(
                    "integration-recipes/python-root-api.json"
                )
                self.assertIsNotNone(root_api)
                root_api_recipe = loads_document(
                    root_api.read().decode("utf-8")
                )
                self.assertEqual(
                    "integration.python.root-api", root_api_recipe.recipe_id,
                )
                self.assertEqual(
                    ("/workspace/api.py", "{port:api}"),
                    root_api_recipe.argv_template,
                )
                self.assertIn(
                    "toolchains/diagnostics/tool.py", archive.getnames(),
                )
                member = archive.extractfile(
                    "engineering-recipes/c-crash_dump.json"
                )
                self.assertIsNotNone(member)
                recipe = loads_document(member.read().decode("utf-8"))
                self.assertIsInstance(recipe, SignedToolRecipe)
                self.assertEqual(1, len(recipe.toolchain_mounts))
                self.assertEqual(
                    ToolchainMountSourceKind.INSTALLED_RELEASE,
                    recipe.toolchain_mounts[0].source_kind,
                )

    def test_portable_signed_bundle_activates_every_component_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            key = Ed25519PrivateKey.generate()
            inputs = []
            for kind in ComponentKind:
                source = root / f"source-{kind.value}"
                source.write_text(kind.value)
                inputs.append(ReleaseBundleInput(kind, "payload", source))
            bundle = root / "bundle"
            manifest = ReleaseBundleBuilder("release-key", key).build(
                "v1", tuple(inputs), bundle,
            )
            self.assertEqual(manifest, load_release_bundle(bundle))
            manager = AtomicReleaseManager(
                root / "installed", {"release-key": key.public_key()},
            )
            receipt = manager.apply(manifest, lambda path: True, source_root=bundle)
            self.assertTrue(receipt.activated)
            active = root / "installed/active"
            self.assertEqual(
                set(ComponentKind),
                {ComponentKind(path.parent.name) for path in active.rglob("payload")},
            )

    def test_bundle_rejects_missing_kind_and_path_escape(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            key = Ed25519PrivateKey.generate()
            source = root / "source"
            source.write_text("value")
            with self.assertRaisesRegex(ValueError, "every component"):
                ReleaseBundleBuilder("key", key).build(
                    "v1", (ReleaseBundleInput(ComponentKind.SERVICE, "service", source),),
                    root / "bundle",
                )


if __name__ == "__main__":
    unittest.main()
