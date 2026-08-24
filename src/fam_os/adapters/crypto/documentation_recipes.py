"""Ed25519 signing for release-owned documentation recipes."""

import base64
import hashlib

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from fam_os.core.engineering.documentation import SignedDocumentationRecipe
from fam_os.core.engineering.documentation_recipes import (
    signed_documentation_recipe_payload,
)
from fam_os.core.engineering.production_documentation_recipes import (
    DocumentationRecipeSpecification,
)


def sign_documentation_recipe_specification(
    specification: DocumentationRecipeSpecification,
    key_id: str,
    private_key: Ed25519PrivateKey,
) -> SignedDocumentationRecipe:
    placeholder = SignedDocumentationRecipe(
        specification.recipe_id, "1.0.0", specification.kind,
        specification.generator_id, specification.output_media_type,
        specification.maximum_source_files, specification.maximum_source_bytes,
        specification.maximum_output_bytes, key_id, "0" * 64,
        base64.b64encode(b"0" * 64).decode("ascii"),
    )
    payload = signed_documentation_recipe_payload(placeholder)
    return SignedDocumentationRecipe(
        placeholder.recipe_id, placeholder.recipe_version, placeholder.kind,
        placeholder.generator_id, placeholder.output_media_type,
        placeholder.maximum_source_files, placeholder.maximum_source_bytes,
        placeholder.maximum_output_bytes, placeholder.signer_key_id,
        hashlib.sha256(payload).hexdigest(),
        base64.b64encode(private_key.sign(payload)).decode("ascii"),
    )
