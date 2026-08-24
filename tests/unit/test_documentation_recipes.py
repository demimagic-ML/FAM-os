import hashlib
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from fam_os.adapters.crypto.documentation_recipes import (
    sign_documentation_recipe_specification,
)
from fam_os.adapters.crypto.engineering_recipes import Ed25519RecipeSignatureVerifier
from fam_os.adapters.documentation import DeterministicDocumentationGenerator
from fam_os.core.engineering import (
    DocumentationArtifactKind, DocumentationGenerationRequest,
    DocumentationGenerationService, DocumentationRequirementPolicy,
    DocumentationSource, DocumentationSourceContent,
    SignedDocumentationRecipeCatalog,
)
from fam_os.core.engineering.production_documentation_recipes import (
    initial_documentation_recipe_specifications,
)
from fam_os.product.natural_engineering_documentation import (
    NaturalEngineeringDocumentationCoordinator,
    UnavailableNaturalEngineeringDocumentationCoordinator,
)


NOW = datetime(2026, 7, 19, 10, 0, tzinfo=timezone.utc)


class DocumentationRecipeTests(unittest.TestCase):
    def setUp(self):
        self.private = Ed25519PrivateKey.from_private_bytes(b"\x02" * 32)
        self.catalog = SignedDocumentationRecipeCatalog(
            Ed25519RecipeSignatureVerifier({
                "release-key": self.private.public_key(),
            }),
        )
        for item in initial_documentation_recipe_specifications():
            self.catalog.admit(sign_documentation_recipe_specification(
                item, "release-key", self.private,
            ))

    def test_signed_catalog_rejects_tampering_and_selects_exact_kind(self):
        selected = self.catalog.select(DocumentationArtifactKind.DIAGRAM)
        self.assertEqual("fam.documentation.diagram@1.0.0", selected.coordinate)
        with self.assertRaisesRegex(ValueError, "payload digest"):
            self.catalog.admit(replace(
                selected, maximum_output_bytes=selected.maximum_output_bytes + 1,
            ))

    def test_bounded_generator_produces_every_declared_artifact_kind(self):
        service = DocumentationGenerationService(
            self.catalog, DeterministicDocumentationGenerator(),
        )
        content = b"def public_api():\n    return 1\n"
        source = DocumentationSource("src/api.py", hashlib.sha256(content).hexdigest())
        for kind in DocumentationArtifactKind:
            with self.subTest(kind=kind.value):
                recipe = service.select(kind)
                request = DocumentationGenerationRequest(
                    f"request-{kind.value}", "task-1", "candidate-1", kind,
                    f"docs/{kind.value}.md", recipe.coordinate,
                    "docs/OWNERS.md", "docs/REGENERATE.md", (source,), NOW,
                )
                selected, output = service.generate(
                    request, (DocumentationSourceContent(source, content),),
                )
                self.assertEqual(recipe, selected)
                self.assertTrue(output)
                output.decode("utf-8", "strict")

    def test_source_digest_and_signed_bounds_are_enforced(self):
        service = DocumentationGenerationService(
            self.catalog, DeterministicDocumentationGenerator(),
        )
        content = b"source"
        source = DocumentationSource("src/api.py", hashlib.sha256(content).hexdigest())
        recipe = service.select(DocumentationArtifactKind.API_REFERENCE)
        request = DocumentationGenerationRequest(
            "request-1", "task-1", "candidate-1",
            DocumentationArtifactKind.API_REFERENCE, "docs/api.md",
            recipe.coordinate, "docs/OWNERS.md", "docs/REGENERATE.md",
            (source,), NOW,
        )
        with self.assertRaisesRegex(ValueError, "digest differs"):
            service.generate(
                request, (DocumentationSourceContent(source, b"changed"),),
            )

    def test_policy_selects_only_relevant_governed_outputs(self):
        policy = DocumentationRequirementPolicy()
        self.assertEqual(
            (
                DocumentationArtifactKind.DIAGRAM,
                DocumentationArtifactKind.API_REFERENCE,
                DocumentationArtifactKind.RUNBOOK,
            ),
            policy.required_kinds(
                "Design an architecture diagram and deploy the API service",
            ),
        )
        self.assertEqual((), policy.required_kinds("Fix a spelling mistake"))

    def test_missing_installed_catalog_fails_relevant_tasks_only(self):
        coordinator = UnavailableNaturalEngineeringDocumentationCoordinator()
        with self.assertRaisesRegex(RuntimeError, "recipes are unavailable"):
            coordinator.generate(
                "owner-1",
                SimpleNamespace(task=SimpleNamespace(intent="Update API docs")),
            )
        self.assertEqual((), coordinator.generate(
            "owner-1",
            SimpleNamespace(task=SimpleNamespace(intent="Fix spelling")),
        ))

    def test_no_required_artifact_is_a_persisted_policy_conclusion(self):
        loop = _SelectionLoop()
        definition = SimpleNamespace(
            created_at=NOW,
            task=SimpleNamespace(task_id="task-1", intent="Fix spelling"),
        )
        coordinator = NaturalEngineeringDocumentationCoordinator(
            loop, SimpleNamespace(),
        )

        self.assertEqual((), coordinator.generate(
            "owner-1", definition, session_id="session-1",
            principal_id="owner-1", preferred_paths=("src/api.py",),
        ))
        self.assertEqual((), loop.selection.required_kinds)
        self.assertEqual(
            "fam.documentation.requirements.v1", loop.selection.policy_id,
        )


class _SelectionLoop:
    def preparation(self, owner_id, task_id):
        return SimpleNamespace(
            candidate=SimpleNamespace(candidate_id="candidate-1"),
        )

    def record_documentation_selection(self, owner_id, selection):
        self.selection = selection
        return selection


if __name__ == "__main__":
    unittest.main()
