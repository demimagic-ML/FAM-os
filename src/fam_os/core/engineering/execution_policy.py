"""Core admission policy for signed recipes and explicitly granted raw shell."""

import base64
import hashlib
import json
from datetime import datetime
from typing import Protocol

from fam_os.core.engineering.authority import EngineeringAuthority
from fam_os.core.engineering.execution import RawShellAuthorization, SignedToolRecipe
from fam_os.core.engineering.grants import EngineeringAuthorityGrant, EngineeringGrantScopeKind


class RecipeSignatureVerifier(Protocol):
    def verify(self, key_id: str, payload: bytes, signature: bytes) -> bool: ...


class SignedToolRecipeCatalog:
    def __init__(self, verifier: RecipeSignatureVerifier) -> None:
        self._verifier = verifier
        self._recipes: dict[tuple[str, str], SignedToolRecipe] = {}

    def admit(self, recipe: SignedToolRecipe) -> None:
        payload = signed_recipe_payload(recipe)
        if hashlib.sha256(payload).hexdigest() != recipe.payload_sha256:
            raise ValueError("signed tool recipe payload digest mismatch")
        signature = base64.b64decode(recipe.signature_base64, validate=True)
        if not self._verifier.verify(recipe.signer_key_id, payload, signature):
            raise PermissionError("signed tool recipe signature is untrusted")
        key = recipe.recipe_id, recipe.recipe_version
        existing = self._recipes.get(key)
        if existing is not None and existing != recipe:
            raise ValueError("signed tool recipe coordinate is immutable")
        self._recipes[key] = recipe

    def get(self, recipe_id: str, recipe_version: str) -> SignedToolRecipe:
        try:
            return self._recipes[(recipe_id, recipe_version)]
        except KeyError as error:
            raise LookupError("signed tool recipe is unavailable") from error

    def matching(
        self, toolchain: str, purposes: tuple,
    ) -> tuple[SignedToolRecipe, ...]:
        """Return only already-admitted signed recipes in deterministic order."""
        if not toolchain.strip() or not purposes or len(set(purposes)) != len(purposes):
            raise ValueError("signed recipe selection query is invalid")
        priority = {purpose: index for index, purpose in enumerate(purposes)}
        values = []
        for recipe in self._recipes.values():
            names = {
                recipe.ecosystem.value,
                recipe.executable_path.rsplit("/", 1)[-1],
            }
            if toolchain in names and recipe.purpose in priority:
                values.append(recipe)
        return tuple(sorted(
            values,
            key=lambda item: (
                priority[item.purpose], item.recipe_id, item.recipe_version,
            ),
        ))

    def matching_purposes(self, purposes: tuple) -> tuple[SignedToolRecipe, ...]:
        """Select admitted recipes by purpose without inventing a toolchain name."""
        if not purposes or len(set(purposes)) != len(purposes):
            raise ValueError("signed recipe purpose selection is invalid")
        priority = {purpose: index for index, purpose in enumerate(purposes)}
        return tuple(sorted(
            (
                recipe for recipe in self._recipes.values()
                if recipe.purpose in priority
            ),
            key=lambda item: (
                priority[item.purpose], item.recipe_id, item.recipe_version,
            ),
        ))


class RawShellGate:
    def authorize(
        self,
        authorization: RawShellAuthorization,
        grant: EngineeringAuthorityGrant,
        command: bytes,
        *,
        principal_id: str,
        task_id: str,
        workspace_root: str,
        instant: datetime,
    ) -> None:
        if not grant.active_at(instant) or grant.grant_id != authorization.grant_id:
            raise PermissionError("raw shell grant is inactive or mismatched")
        if EngineeringAuthority.RAW_SHELL not in grant.authorities:
            raise PermissionError("raw shell authority was not granted")
        if grant.principal_id != principal_id or authorization.principal_id != principal_id:
            raise PermissionError("raw shell principal is mismatched")
        if authorization.task_id != task_id:
            raise PermissionError("raw shell task is mismatched")
        if grant.scope.kind is not EngineeringGrantScopeKind.TASK or grant.scope.scope_id != task_id:
            raise PermissionError("raw shell grant must bind the exact task")
        if workspace_root not in grant.scope.workspace_roots or authorization.workspace_root != workspace_root:
            raise PermissionError("raw shell workspace is mismatched")
        if not authorization.issued_at <= instant < authorization.expires_at:
            raise PermissionError("raw shell authorization is expired")
        if hashlib.sha256(command).hexdigest() != authorization.command_sha256:
            raise PermissionError("raw shell command is not the approved command")


def signed_recipe_payload(recipe: SignedToolRecipe) -> bytes:
    document = {
        "allowed_environment_keys": list(recipe.allowed_environment_keys),
        "argv_template": list(recipe.argv_template),
        "ecosystem": recipe.ecosystem.value,
        "executable_path": recipe.executable_path,
        "expected_exit_codes": list(recipe.expected_exit_codes),
        "network_mode": recipe.network_mode.value,
        "purpose": recipe.purpose.value,
        "recipe_id": recipe.recipe_id,
        "recipe_version": recipe.recipe_version,
        "signer_key_id": recipe.signer_key_id,
        "toolchain_mounts": [
            {
                "sandbox_path": item.sandbox_path,
                "source_path": item.source_path,
                "tree_sha256": item.tree_sha256,
                **(
                    {}
                    if item.source_kind.value == "host_absolute"
                    else {"source_kind": item.source_kind.value}
                ),
            }
            for item in recipe.toolchain_mounts
        ],
        "verifier_ids": list(recipe.verifier_ids),
    }
    return json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
