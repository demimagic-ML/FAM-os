"""Release-signed independent reviewer admission and execution."""

from __future__ import annotations

import base64
import hashlib
import json
from typing import Protocol

from fam_os.core.engineering.review import (
    EngineeringReviewCheckpoint,
    EngineeringReviewSelection,
    SignedEngineeringReviewerRecipe,
)


class EngineeringReviewerRecipeSignatureVerifier(Protocol):
    def verify(self, key_id: str, payload: bytes, signature: bytes) -> bool: ...


class EngineeringReviewerAdapter(Protocol):
    def review(
        self, recipe: SignedEngineeringReviewerRecipe,
        selection: EngineeringReviewSelection,
        changeset,
        *, producer_id: str,
    ) -> EngineeringReviewCheckpoint: ...


class SignedEngineeringReviewerCatalog:
    def __init__(self, verifier: EngineeringReviewerRecipeSignatureVerifier) -> None:
        self._verifier = verifier
        self._recipes: dict[str, SignedEngineeringReviewerRecipe] = {}

    def admit(self, recipe: SignedEngineeringReviewerRecipe) -> None:
        payload = signed_engineering_reviewer_payload(recipe)
        if hashlib.sha256(payload).hexdigest() != recipe.payload_sha256:
            raise ValueError("signed reviewer recipe payload digest mismatch")
        signature = base64.b64decode(recipe.signature_base64, validate=True)
        if not self._verifier.verify(recipe.signer_key_id, payload, signature):
            raise PermissionError("signed reviewer recipe is untrusted")
        existing = self._recipes.get(recipe.coordinate)
        if existing is not None and existing != recipe:
            raise ValueError("signed reviewer recipe coordinate is immutable")
        self._recipes[recipe.coordinate] = recipe

    def select(self, disciplines) -> SignedEngineeringReviewerRecipe:
        required = frozenset(disciplines)
        matches = sorted(
            (
                item for item in self._recipes.values()
                if required.issubset(item.disciplines)
            ),
            key=lambda item: (len(item.disciplines), item.recipe_id, item.recipe_version),
        )
        if not matches:
            raise LookupError("no signed reviewer covers the selected disciplines")
        return matches[0]


class EngineeringReviewExecutionService:
    def __init__(
        self, catalog: SignedEngineeringReviewerCatalog,
        adapter: EngineeringReviewerAdapter,
    ) -> None:
        self._catalog = catalog
        self._adapter = adapter

    def review(
        self, selection: EngineeringReviewSelection, changeset, *, producer_id: str,
    ) -> EngineeringReviewCheckpoint:
        recipe = self._catalog.select(selection.required_disciplines)
        checkpoint = self._adapter.review(
            recipe, selection, changeset, producer_id=producer_id,
        )
        if (
            checkpoint.task_id != selection.task_id
            or checkpoint.candidate_id != selection.candidate_id
            or checkpoint.changeset_sha256 != selection.changeset_sha256
            or checkpoint.required_disciplines != selection.required_disciplines
            or checkpoint.reviewer_id != recipe.reviewer_id
            or checkpoint.producer_id != producer_id
            or recipe.coordinate not in checkpoint.reviewer_independence_ref
        ):
            raise PermissionError("signed reviewer returned an unbound checkpoint")
        return checkpoint


def signed_engineering_reviewer_payload(
    recipe: SignedEngineeringReviewerRecipe,
) -> bytes:
    return json.dumps({
        "adapter_id": recipe.adapter_id,
        "disciplines": [item.value for item in recipe.disciplines],
        "recipe_id": recipe.recipe_id,
        "recipe_version": recipe.recipe_version,
        "reviewer_id": recipe.reviewer_id,
        "signer_key_id": recipe.signer_key_id,
    }, sort_keys=True, separators=(",", ":")).encode()
