import hashlib
import io
import json
import tarfile
import tempfile
import unittest
from dataclasses import replace
from importlib import resources
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from fam_os.product.atomic_update import AtomicReleaseManager
from fam_os.product.composition.catalog_unit import _configured_catalog
from fam_os.product.composition.verifier_unit import production_verifier_catalog
from fam_os.core.production import ModelIntent, RuntimeModelEntry
from fam_os.core.production.model_catalog import (
    RuntimeModelCatalog,
    RuntimeModelProvenance,
)
from fam_os.core.production.model_catalog_scopes import validated_expert_scopes
from fam_os.core.engineering import EngineeringAuthority
from tests.contract.schema_manifest_fixtures import (
    expert_manifest,
    expert_runtime_binding,
)
from fam_os.product.update_contracts import ComponentKind, ReleaseComponent
from fam_os.product.update_signing import sign_manifest


ROOT = Path(__file__).parents[2]
MODEL_REF = "nomic-embed-text:latest"


class PackagedRuntimeCatalogTests(unittest.TestCase):
    def test_packaged_catalog_is_exact_copy_of_canonical_configuration(self) -> None:
        canonical = ROOT / "configs/packages/runtime/model-catalog.json"
        packaged = resources.files("fam_os.product.resources").joinpath(
            "runtime", "model-catalog.json",
        )
        self.assertEqual(canonical.read_bytes(), packaged.read_bytes())

    def test_signed_code_scope_declares_all_advisory_authorities_without_granting_them(self) -> None:
        manifest = expert_manifest()
        binding = expert_runtime_binding()
        coordinate = (
            manifest.package.package_id,
            manifest.package.package_version,
            manifest.expert_id,
        )
        document = {
            "models": [{
                "model_ref": binding.artifact_ref,
                "expert_scopes": [{
                    "expert_id": manifest.expert_id,
                    "package_id": manifest.package.package_id,
                    "package_version": manifest.package.package_version,
                    "intents": ["code"],
                    "verifier_ids": list(manifest.required_verifier_ids),
                    "advisory_authorities": [
                        authority.value for authority in EngineeringAuthority
                    ],
                }],
            }],
        }
        scopes, _selected = validated_expert_scopes(
            document, {coordinate: (manifest, binding)}, {binding.artifact_ref},
        )

        scope = scopes[manifest.expert_id]
        self.assertEqual(set(EngineeringAuthority), set(scope.advisory_authorities))
        self.assertFalse(hasattr(scope, "grant_id"))

    def test_non_code_signed_scope_cannot_claim_engineering_advice(self) -> None:
        manifest = replace(expert_manifest(), capabilities=("language.generate",))
        binding = expert_runtime_binding()
        coordinate = (
            manifest.package.package_id,
            manifest.package.package_version,
            manifest.expert_id,
        )
        document = {
            "models": [{
                "model_ref": binding.artifact_ref,
                "expert_scopes": [{
                    "expert_id": manifest.expert_id,
                    "package_id": manifest.package.package_id,
                    "package_version": manifest.package.package_version,
                    "intents": ["conversation"],
                    "verifier_ids": list(manifest.required_verifier_ids),
                    "advisory_authorities": [EngineeringAuthority.MODIFY.value],
                }],
            }],
        }
        with self.assertRaisesRegex(ValueError, "lacks a code capability"):
            validated_expert_scopes(
                document, {coordinate: (manifest, binding)}, {binding.artifact_ref},
            )

    def test_runtime_verifier_declarations_are_activated_production_ids(self) -> None:
        document = json.loads(
            (ROOT / "configs/packages/runtime/model-catalog.json").read_text(
                encoding="utf-8",
            )
        )
        available = set(production_verifier_catalog().verifier_ids())
        declared = {
            verifier_id
            for model in document["models"]
            for verifier_id in model.get("verifier_ids", ())
        }

        self.assertTrue(declared)
        self.assertLessEqual(declared, available)
        self.assertNotIn("python-tests", declared)
        self.assertNotIn("application-postcondition", declared)

    def test_wheel_style_root_uses_packaged_catalog_for_present_models(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model_root = root / "models"
            _write_model(model_root, MODEL_REF)

            catalog = _configured_catalog(root / "wheel-root", model_root)

        self.assertIsNotNone(catalog)
        assert catalog is not None
        entries = catalog.entries()
        self.assertEqual((MODEL_REF,), tuple(item.model_ref for item in entries))
        self.assertEqual("embedding", entries[0].tier)
        self.assertGreater(entries[0].estimated_resident_bytes, 0)

    def test_catalog_rejects_unavailable_declared_verifier(self) -> None:
        catalog = RuntimeModelCatalog((_entry(("verifier.unavailable",)),))

        with self.assertRaisesRegex(ValueError, "requires unavailable verifiers"):
            catalog.require_available_verifiers(("verifier.available",))

    def test_runtime_catalog_rejects_duplicate_json_keys(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "model-catalog.json"
            config.write_text(
                '{"contract_version":"fam.product.model-catalog/v1alpha1",'
                '"contract_version":"fam.product.model-catalog/v1alpha1",'
                '"models":[]}',
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "strict JSON"):
                RuntimeModelCatalog.from_source(config, root / "models")

    def test_runtime_catalog_rejects_ambiguous_provider_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model_root = root / "models"
            _write_model(model_root, MODEL_REF, duplicate_manifest_keys=True)

            with self.assertRaisesRegex(ValueError, "manifest must be strict JSON"):
                _configured_catalog(root / "wheel-root", model_root)

    def test_bound_catalog_rejects_incompatible_dynamic_model(self) -> None:
        catalog = RuntimeModelCatalog(())
        catalog.require_available_verifiers(("verifier.available",))

        with self.assertRaisesRegex(ValueError, "verifier.unavailable"):
            catalog.install_runtime_model(
                _entry(("verifier.unavailable",), model_ref="dynamic:model"),
                RuntimeModelProvenance(
                    "dynamic:model", "expert.dynamic", "package@1.0.0",
                    "ollama.local/v1:dynamic:model",
                ),
            )

        self.assertIsNone(catalog.get("dynamic:model"))

    def test_enabled_catalog_preserves_verifier_invariant(self) -> None:
        model = _entry(("verifier.available",))
        provenance = RuntimeModelProvenance(
            model.model_ref, "expert.test", "package@1.0.0",
            "ollama.local/v1:test:model",
        )
        catalog = RuntimeModelCatalog((model,), (provenance,))
        catalog.require_available_verifiers(("verifier.available",))
        enabled = catalog.enabled({"expert.test"})

        with self.assertRaisesRegex(ValueError, "verifier.unavailable"):
            enabled.install_runtime_model(
                _entry(("verifier.unavailable",), model_ref="dynamic:model"),
                RuntimeModelProvenance(
                    "dynamic:model", "expert.dynamic", "package@1.0.0",
                    "ollama.local/v1:dynamic:model",
                ),
            )

    def test_signed_catalog_retains_every_shared_model_expert_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = _signed_llama_catalog(Path(directory))

        self.assertEqual(
            {
                "expert.language.llama3.2-3b",
                "expert.math.llama3.2-reasoning",
                "expert.retrieval.llama3.2-synthesis",
            },
            {item.expert_id for item in catalog.provenances()},
        )
        self.assertEqual(
            {
                "verifier.text.exact-v1",
                "retrieval.citations.v1",
                "math.sympy-equivalence.v1",
            },
            set(catalog.entries()[0].verifier_ids),
        )
        language = catalog.enabled({"expert.language.llama3.2-3b"})
        self.assertEqual(
            (ModelIntent.CONVERSATION,), language.entries()[0].intents,
        )
        self.assertEqual(
            ("verifier.text.exact-v1",), language.entries()[0].verifier_ids,
        )
        self.assertEqual(
            ("expert.language.llama3.2-3b",),
            tuple(item.expert_id for item in language.provenances()),
        )

    def test_signed_catalog_rejects_verifier_not_declared_by_bound_experts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "claims undeclared verifiers"):
                _signed_llama_catalog(
                    Path(directory),
                    retrieval_verifier_id="verifier.not-declared",
                )

    def test_signed_catalog_requires_an_exact_package_coordinate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "exact signed package binding"):
                _signed_llama_catalog(
                    Path(directory), language_package_version="1.0.10",
                )

    def test_signed_catalog_rejects_omitted_required_expert_verifier(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "omits required verifiers"):
                _signed_llama_catalog(
                    Path(directory), language_verifier_ids=(),
                )

    def test_signed_catalog_rejects_duplicate_archive_member_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "duplicate member paths"):
                _signed_llama_catalog(
                    Path(directory), duplicate_catalog_member=True,
                )


def _write_model(
    root: Path, model_ref: str, *, duplicate_manifest_keys: bool = False,
) -> None:
    content = b"packaged-runtime-catalog-test"
    digest = hashlib.sha256(content).hexdigest()
    blob = root / "blobs" / f"sha256-{digest}"
    blob.parent.mkdir(parents=True)
    blob.write_bytes(content)
    name, tag = model_ref.split(":", maxsplit=1)
    manifest = root / "manifests/registry.ollama.ai/library" / name / tag
    manifest.parent.mkdir(parents=True)
    document = json.dumps({
        "config": {"digest": f"sha256:{digest}"},
        "layers": [],
    })
    if duplicate_manifest_keys:
        document = document[:-1] + ', "layers": []}'
    manifest.write_text(document, encoding="utf-8")


def _entry(verifier_ids, model_ref="test:model") -> RuntimeModelEntry:
    return RuntimeModelEntry(
        model_ref, "economical", (ModelIntent.CODE,), 1024**3, 8192,
        "0" * 64, tuple(verifier_ids),
    )


def _signed_llama_catalog(
    root: Path,
    *,
    retrieval_verifier_id="retrieval.citations.v1",
    language_package_version="1.0.0",
    language_verifier_ids=("verifier.text.exact-v1",),
    duplicate_catalog_member=False,
) -> RuntimeModelCatalog:
    model_ref = "llama3.2:3b"
    model_root = root / "models"
    _write_model(model_root, model_ref)
    expert_archive = root / "expert.tar"
    package_root = ROOT / "configs/packages"
    names = (
        "language-llama3.2-3b.json",
        "math-llama3.2-reasoning.json",
        "retrieval-llama3.2-synthesis.json",
    )
    runtime_document = json.dumps({
        "contract_version": "fam.product.model-catalog/v1alpha1",
        "models": [{
            "model_ref": model_ref,
            "tier": "economical",
            "intents": ["conversation", "math", "retrieval"],
            "max_context_tokens": 4096,
            "verifier_ids": [
                *language_verifier_ids,
                retrieval_verifier_id,
                "math.sympy-equivalence.v1",
            ],
            "expert_scopes": [
                {
                    "expert_id": "expert.language.llama3.2-3b",
                    "package_id": "fam.expert.language.llama3.2-3b",
                    "package_version": language_package_version,
                    "intents": ["conversation"],
                    "verifier_ids": list(language_verifier_ids),
                },
                {
                    "expert_id": "expert.math.llama3.2-reasoning",
                    "package_id": "fam.expert.math.llama3.2-reasoning",
                    "package_version": "1.0.0",
                    "intents": ["math"],
                    "verifier_ids": ["math.sympy-equivalence.v1"],
                },
                {
                    "expert_id": "expert.retrieval.llama3.2-synthesis",
                    "package_id": "fam.expert.retrieval.llama3.2-synthesis",
                    "package_version": "1.0.0",
                    "intents": ["retrieval"],
                    "verifier_ids": [retrieval_verifier_id],
                },
            ],
        }],
    }).encode("utf-8")
    with tarfile.open(expert_archive, "w") as archive:
        info = tarfile.TarInfo("runtime/model-catalog.json")
        info.size = len(runtime_document)
        archive.addfile(info, io.BytesIO(runtime_document))
        if duplicate_catalog_member:
            duplicate = tarfile.TarInfo("runtime/model-catalog.json")
            duplicate.size = len(runtime_document)
            archive.addfile(duplicate, io.BytesIO(runtime_document))
        for name in names:
            archive.add(package_root / "experts" / name, arcname=f"experts/{name}")
            archive.add(package_root / "bindings" / name, arcname=f"bindings/{name}")
    key = Ed25519PrivateKey.generate()
    components = []
    for kind in ComponentKind:
        source = expert_archive if kind is ComponentKind.EXPERT else root / kind.value
        if kind is not ComponentKind.EXPERT:
            source.write_text(kind.value, encoding="utf-8")
        components.append(ReleaseComponent(
            kind, source.name, str(source), hashlib.sha256(source.read_bytes()).hexdigest(),
        ))
    manifest = sign_manifest("signed-catalog-test", tuple(components), "key", key)
    installed = root / "installed"
    AtomicReleaseManager(installed, {"key": key.public_key()}).apply(manifest, lambda _: True)
    trust = installed / "trust"
    trust.mkdir()
    (trust / "key.pem").write_bytes(key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ))
    return RuntimeModelCatalog.from_signed_release(
        (installed / "active").resolve(), trust, model_root,
    )


if __name__ == "__main__":
    unittest.main()
