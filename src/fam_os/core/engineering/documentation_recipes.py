"""Trusted selection and bounded execution policy for documentation recipes."""

from dataclasses import dataclass
import base64
import hashlib
import json
from typing import Protocol

from fam_os.core.engineering.documentation import (
    DocumentationArtifactKind, DocumentationGenerationRequest,
    DocumentationSource, SignedDocumentationRecipe,
)


class DocumentationRecipeSignatureVerifier(Protocol):
    def verify(self, key_id: str, payload: bytes, signature: bytes) -> bool: ...


class DocumentationGenerator(Protocol):
    def generate(
        self, recipe: SignedDocumentationRecipe,
        request: DocumentationGenerationRequest,
        sources: tuple["DocumentationSourceContent", ...],
    ) -> bytes: ...


@dataclass(frozen=True, slots=True)
class DocumentationSourceContent:
    source: DocumentationSource
    content: bytes


class SignedDocumentationRecipeCatalog:
    def __init__(self, verifier: DocumentationRecipeSignatureVerifier) -> None:
        self._verifier = verifier
        self._recipes: dict[str, SignedDocumentationRecipe] = {}

    def admit(self, recipe: SignedDocumentationRecipe) -> None:
        payload = signed_documentation_recipe_payload(recipe)
        if hashlib.sha256(payload).hexdigest() != recipe.payload_sha256:
            raise ValueError("signed documentation recipe payload digest mismatch")
        signature = base64.b64decode(recipe.signature_base64, validate=True)
        if not self._verifier.verify(recipe.signer_key_id, payload, signature):
            raise PermissionError("signed documentation recipe is untrusted")
        existing = self._recipes.get(recipe.coordinate)
        if existing is not None and existing != recipe:
            raise ValueError("signed documentation recipe coordinate is immutable")
        self._recipes[recipe.coordinate] = recipe

    def get(self, coordinate: str) -> SignedDocumentationRecipe:
        try:
            return self._recipes[coordinate]
        except KeyError as error:
            raise LookupError("signed documentation recipe is unavailable") from error

    def select(self, kind: DocumentationArtifactKind) -> SignedDocumentationRecipe:
        matches = sorted(
            (item for item in self._recipes.values() if item.kind is kind),
            key=lambda item: (item.recipe_id, item.recipe_version),
        )
        if not matches:
            raise LookupError(f"no signed documentation recipe for {kind.value}")
        return matches[0]


class DocumentationGenerationService:
    def __init__(
        self, catalog: SignedDocumentationRecipeCatalog,
        generator: DocumentationGenerator,
    ) -> None:
        self._catalog = catalog
        self._generator = generator

    def select(self, kind: DocumentationArtifactKind) -> SignedDocumentationRecipe:
        return self._catalog.select(kind)

    def generate(
        self, request: DocumentationGenerationRequest,
        sources: tuple[DocumentationSourceContent, ...],
    ) -> tuple[SignedDocumentationRecipe, bytes]:
        recipe = self._catalog.get(request.generator_recipe_id)
        if recipe.kind is not request.kind:
            raise PermissionError("documentation recipe kind differs from request")
        if tuple(item.source for item in sources) != request.sources:
            raise ValueError("documentation source content differs from request")
        if len(sources) > recipe.maximum_source_files:
            raise PermissionError("documentation source count exceeds signed recipe")
        if sum(len(item.content) for item in sources) > recipe.maximum_source_bytes:
            raise PermissionError("documentation sources exceed signed recipe")
        for item in sources:
            if hashlib.sha256(item.content).hexdigest() != item.source.content_sha256:
                raise ValueError("documentation source content digest differs")
        output = self._generator.generate(recipe, request, sources)
        if not isinstance(output, bytes):
            raise TypeError("documentation generator output must be bytes")
        if len(output) > recipe.maximum_output_bytes:
            raise PermissionError("documentation output exceeds signed recipe")
        output.decode("utf-8", "strict")
        return recipe, output


def signed_documentation_recipe_payload(recipe: SignedDocumentationRecipe) -> bytes:
    return json.dumps({
        "generator_id": recipe.generator_id,
        "kind": recipe.kind.value,
        "maximum_output_bytes": recipe.maximum_output_bytes,
        "maximum_source_bytes": recipe.maximum_source_bytes,
        "maximum_source_files": recipe.maximum_source_files,
        "output_media_type": recipe.output_media_type,
        "recipe_id": recipe.recipe_id,
        "recipe_version": recipe.recipe_version,
        "signer_key_id": recipe.signer_key_id,
    }, sort_keys=True, separators=(",", ":")).encode()
