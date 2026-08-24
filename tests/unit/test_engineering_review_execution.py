import unittest
from dataclasses import replace

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from fam_os.adapters.crypto.engineering_recipes import (
    Ed25519RecipeSignatureVerifier,
)
from fam_os.adapters.crypto.review_recipes import (
    sign_engineering_reviewer_recipe_specification,
)
from fam_os.adapters.review import DeterministicEngineeringReviewer
from fam_os.core.engineering import (
    EngineeringReviewDiscipline,
    EngineeringReviewExecutionService,
    EngineeringReviewSelectionPolicy,
    EngineeringReviewStatus,
    SignedEngineeringReviewerCatalog,
    engineering_task_digest,
)
from fam_os.core.engineering.production_review_recipes import (
    initial_engineering_reviewer_recipe_specification,
)
from tests.contract.schema_candidate_changeset_fixtures import (
    candidate_changeset_schema_values,
)
from tests.contract.schema_task_definition_fixtures import (
    task_definition_schema_values,
)


class EngineeringReviewExecutionTests(unittest.TestCase):
    def test_policy_selects_all_disciplines_and_signed_reviewer_blocks_risks(self):
        task = task_definition_schema_values()[0]
        envelope = replace(
            task.task,
            intent=(
                "Redesign the UI security architecture and migrate the schema"
            ),
        )
        task = replace(
            task, task=envelope, task_sha256=engineering_task_digest(envelope),
        )
        changeset = candidate_changeset_schema_values()[0]
        item = replace(
            changeset.preview.items[0],
            path="src/fam_os/schemas/new.py",
            risk_codes=("set_executable",),
        )
        changeset = replace(
            changeset,
            preview=replace(changeset.preview, items=(item,)),
        )
        selection = EngineeringReviewSelectionPolicy().select(task, changeset)
        self.assertEqual(tuple(EngineeringReviewDiscipline), selection.required_disciplines)

        key = Ed25519PrivateKey.generate()
        recipe = sign_engineering_reviewer_recipe_specification(
            initial_engineering_reviewer_recipe_specification(), "release", key,
        )
        catalog = SignedEngineeringReviewerCatalog(
            Ed25519RecipeSignatureVerifier({"release": key.public_key()}),
        )
        catalog.admit(recipe)
        checkpoint = EngineeringReviewExecutionService(
            catalog, DeterministicEngineeringReviewer(),
        ).review(selection, changeset, producer_id="generation-1")
        self.assertEqual(EngineeringReviewStatus.BLOCKED, checkpoint.status)
        self.assertEqual(
            {EngineeringReviewDiscipline.SECURITY, EngineeringReviewDiscipline.ARCHITECTURE},
            {item.discipline for item in checkpoint.findings},
        )
        self.assertIn(recipe.coordinate, checkpoint.reviewer_independence_ref)
        self.assertNotEqual(checkpoint.producer_id, checkpoint.reviewer_id)

    def test_catalog_rejects_recipe_signed_outside_release_trust(self):
        trusted = Ed25519PrivateKey.generate()
        untrusted = Ed25519PrivateKey.generate()
        recipe = sign_engineering_reviewer_recipe_specification(
            initial_engineering_reviewer_recipe_specification(),
            "release", untrusted,
        )
        catalog = SignedEngineeringReviewerCatalog(
            Ed25519RecipeSignatureVerifier({"release": trusted.public_key()}),
        )
        with self.assertRaisesRegex(PermissionError, "untrusted"):
            catalog.admit(recipe)


if __name__ == "__main__":
    unittest.main()
