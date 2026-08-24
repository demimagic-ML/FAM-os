"""Ed25519 signing and trusted-key verification for engineering recipes."""

import base64
import hashlib

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from fam_os.core.engineering.execution import SignedToolRecipe, ToolchainMount
from fam_os.core.engineering.execution_policy import signed_recipe_payload
from fam_os.core.engineering.production_recipes import ToolRecipeSpecification


class Ed25519RecipeSignatureVerifier:
    def __init__(self, trusted_keys: dict[str, Ed25519PublicKey]) -> None:
        if not trusted_keys:
            raise ValueError("recipe verifier requires trusted keys")
        self._trusted_keys = dict(trusted_keys)

    def verify(self, key_id: str, payload: bytes, signature: bytes) -> bool:
        key = self._trusted_keys.get(key_id)
        if key is None:
            return False
        try:
            key.verify(signature, payload)
        except (InvalidSignature, ValueError):
            return False
        return True


def sign_recipe_specification(
    specification: ToolRecipeSpecification,
    key_id: str,
    private_key: Ed25519PrivateKey,
    *,
    toolchain_mounts: tuple[ToolchainMount, ...] = (),
) -> SignedToolRecipe:
    """Bind one release recipe specification to an immutable signature."""
    placeholder = SignedToolRecipe(
        specification.recipe_id or
        f"engineering.{specification.ecosystem.value}.{specification.purpose.value}",
        "1.0.0",
        specification.ecosystem,
        specification.purpose,
        specification.executable_path,
        specification.argv,
        (),
        (0,),
        (specification.verifier_id,),
        key_id,
        "0" * 64,
        base64.b64encode(b"0" * 64).decode("ascii"),
        toolchain_mounts,
    )
    payload = signed_recipe_payload(placeholder)
    return SignedToolRecipe(
        placeholder.recipe_id,
        placeholder.recipe_version,
        placeholder.ecosystem,
        placeholder.purpose,
        placeholder.executable_path,
        placeholder.argv_template,
        placeholder.allowed_environment_keys,
        placeholder.expected_exit_codes,
        placeholder.verifier_ids,
        key_id,
        hashlib.sha256(payload).hexdigest(),
        base64.b64encode(private_key.sign(payload)).decode("ascii"),
        toolchain_mounts,
    )
