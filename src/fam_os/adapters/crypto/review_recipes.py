"""Ed25519 signing for release-owned engineering reviewer recipes."""

import base64
import hashlib

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from fam_os.core.engineering.production_review_recipes import (
    EngineeringReviewerRecipeSpecification,
)
from fam_os.core.engineering.review import SignedEngineeringReviewerRecipe
from fam_os.core.engineering.review_recipes import (
    signed_engineering_reviewer_payload,
)


def sign_engineering_reviewer_recipe_specification(
    specification: EngineeringReviewerRecipeSpecification,
    key_id: str,
    private_key: Ed25519PrivateKey,
) -> SignedEngineeringReviewerRecipe:
    placeholder = SignedEngineeringReviewerRecipe(
        specification.recipe_id, "1.0.0", specification.reviewer_id,
        specification.adapter_id, specification.disciplines, key_id,
        "0" * 64, base64.b64encode(b"0" * 64).decode("ascii"),
    )
    payload = signed_engineering_reviewer_payload(placeholder)
    return SignedEngineeringReviewerRecipe(
        placeholder.recipe_id, placeholder.recipe_version,
        placeholder.reviewer_id, placeholder.adapter_id,
        placeholder.disciplines, key_id,
        hashlib.sha256(payload).hexdigest(),
        base64.b64encode(private_key.sign(payload)).decode("ascii"),
    )
