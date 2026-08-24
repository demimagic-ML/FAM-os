import hashlib
import io
import tempfile
import tarfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from fam_os.adapters.crypto.engineering_recipes import sign_recipe_specification
from fam_os.adapters.crypto.documentation_recipes import (
    sign_documentation_recipe_specification,
)
from fam_os.adapters.crypto.review_recipes import (
    sign_engineering_reviewer_recipe_specification,
)
from fam_os.core.engineering import (
    DocumentationArtifactKind, EngineeringEcosystem, ToolRecipePurpose,
)
from fam_os.core.engineering.production_documentation_recipes import (
    DocumentationRecipeSpecification,
)
from fam_os.core.engineering.production_recipes import ToolRecipeSpecification
from fam_os.core.engineering.production_review_recipes import (
    initial_engineering_reviewer_recipe_specification,
)
from fam_os.product.atomic_update import AtomicReleaseManager
from fam_os.product.composition.integration_recipes import (
    installed_engineering_recipe_catalog, installed_integration_recipe_catalog,
)
from fam_os.product.composition.documentation_recipes import (
    installed_documentation_recipe_catalog,
)
from fam_os.product.composition.review_recipes import (
    installed_engineering_reviewer_catalog,
)
from fam_os.product.composition.integration_environment import compose_integration_environment
from fam_os.product.update_contracts import ComponentKind, ReleaseComponent
from fam_os.product.update_signing import sign_manifest
from fam_os.schemas import dumps_document


class InstalledIntegrationRecipeTests(unittest.TestCase):
    def test_only_release_signed_recipe_is_admitted_from_verified_archive(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            key = Ed25519PrivateKey.generate()
            release = _installed_release(root, key, key)
            catalog = installed_integration_recipe_catalog(release)
            recipe = catalog.get("engineering.python.acceptance", "1.0.0")
            self.assertEqual(("/workspace/.fam/services/api.py", "{port:api}"), recipe.argv_template)
            unit = compose_integration_environment(
                object(), docker_executable=root / "missing-docker",
                process_recipes=catalog,
            )
            self.assertIsNotNone(unit)
            self.assertIsNone(unit.adapter.docker)
            self.assertIsNotNone(unit.adapter.process)

    def test_recipe_signed_by_different_key_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            release_key = Ed25519PrivateKey.generate()
            recipe_key = Ed25519PrivateKey.generate()
            release = _installed_release(root, release_key, recipe_key)
            with self.assertRaisesRegex(PermissionError, "signer differs"):
                installed_integration_recipe_catalog(release)

    def test_release_signed_engineering_recipe_is_loaded_separately(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            key = Ed25519PrivateKey.generate()
            release = _installed_release(
                root, key, key, "engineering-recipes/python-acceptance.json",
            )
            catalog = installed_engineering_recipe_catalog(release)
            self.assertIsNotNone(catalog)
            self.assertEqual(
                "engineering.python.acceptance",
                catalog.get("engineering.python.acceptance", "1.0.0").recipe_id,
            )
            self.assertIsNone(installed_integration_recipe_catalog(release))

    def test_release_signed_documentation_recipe_is_loaded_separately(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            key = Ed25519PrivateKey.generate()
            recipe = sign_documentation_recipe_specification(
                DocumentationRecipeSpecification(
                    "fam.documentation.api_reference",
                    DocumentationArtifactKind.API_REFERENCE,
                    "fam.documentation.deterministic.v1", "text/markdown",
                ),
                "release", key,
            )
            release = _installed_payload_release(
                root, key, recipe,
                "documentation-recipes/api_reference.json",
            )
            catalog = installed_documentation_recipe_catalog(release)
            self.assertIsNotNone(catalog)
            self.assertEqual(recipe, catalog.select(
                DocumentationArtifactKind.API_REFERENCE,
            ))
            self.assertIsNone(installed_engineering_recipe_catalog(release))

    def test_release_signed_independent_reviewer_is_loaded_separately(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            key = Ed25519PrivateKey.generate()
            recipe = sign_engineering_reviewer_recipe_specification(
                initial_engineering_reviewer_recipe_specification(),
                "release", key,
            )
            release = _installed_payload_release(
                root, key, recipe, "review-recipes/independent.json",
            )
            catalog = installed_engineering_reviewer_catalog(release)
            self.assertIsNotNone(catalog)
            self.assertEqual(recipe, catalog.select(recipe.disciplines))
            self.assertIsNone(installed_documentation_recipe_catalog(release))


def _installed_release(
    root, release_key, recipe_key,
    member_name="integration-recipes/python-http.json",
):
    specification = ToolRecipeSpecification(
        EngineeringEcosystem.PYTHON, ToolRecipePurpose.ACCEPTANCE,
        "/usr/bin/python3", ("/workspace/.fam/services/api.py", "{port:api}"),
        "integration.http.health.v1",
    )
    signer_id = "release" if recipe_key is release_key else "other"
    recipe = sign_recipe_specification(specification, signer_id, recipe_key)
    expert = root / "experts.tar"
    payload = (dumps_document(recipe) + "\n").encode()
    with tarfile.open(expert, "w") as archive:
        info = tarfile.TarInfo(member_name)
        info.size = len(payload); archive.addfile(info, io.BytesIO(payload))
    components = []
    for kind in ComponentKind:
        source = expert if kind is ComponentKind.EXPERT else root / kind.value
        if kind is not ComponentKind.EXPERT:
            source.write_text(kind.value)
        components.append(ReleaseComponent(
            kind, source.name, str(source), hashlib.sha256(source.read_bytes()).hexdigest(),
        ))
    manifest = sign_manifest("integration-recipes", tuple(components), "release", release_key)
    prefix = root / "installed"
    AtomicReleaseManager(prefix, {"release": release_key.public_key()}).apply(manifest, lambda _: True)
    trust = prefix / "trust"; trust.mkdir()
    (trust / "release.pem").write_bytes(release_key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
    ))
    return (prefix / "active").resolve()


def _installed_payload_release(root, key, value, member_name):
    expert = root / "experts.tar"
    payload = (dumps_document(value) + "\n").encode()
    with tarfile.open(expert, "w") as archive:
        info = tarfile.TarInfo(member_name)
        info.size = len(payload)
        archive.addfile(info, io.BytesIO(payload))
    components = []
    for kind in ComponentKind:
        source = expert if kind is ComponentKind.EXPERT else root / kind.value
        if kind is not ComponentKind.EXPERT:
            source.write_text(kind.value)
        components.append(ReleaseComponent(
            kind, source.name, str(source),
            hashlib.sha256(source.read_bytes()).hexdigest(),
        ))
    manifest = sign_manifest(
        "documentation-recipes", tuple(components), "release", key,
    )
    prefix = root / "installed"
    AtomicReleaseManager(prefix, {"release": key.public_key()}).apply(
        manifest, lambda _: True,
    )
    trust = prefix / "trust"
    trust.mkdir()
    (trust / "release.pem").write_bytes(key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ))
    return (prefix / "active").resolve()


if __name__ == "__main__": unittest.main()
