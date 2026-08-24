"""Load release-signed integration recipes from the verified expert archive."""

from pathlib import Path
import tarfile

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from fam_os.adapters.crypto.engineering_recipes import Ed25519RecipeSignatureVerifier
from fam_os.core.engineering import SignedToolRecipe
from fam_os.core.engineering.execution_policy import SignedToolRecipeCatalog
from fam_os.product.release_trust import verify_installed_release
from fam_os.product.update_contracts import ComponentKind
from fam_os.schemas import loads_document


def installed_integration_recipe_catalog(
    release_root: Path,
) -> SignedToolRecipeCatalog | None:
    return _installed_recipe_catalog(release_root, ("integration-recipes/",))


def installed_engineering_recipe_catalog(
    release_root: Path,
) -> SignedToolRecipeCatalog | None:
    return _installed_recipe_catalog(release_root, ("engineering-recipes/",))


def _installed_recipe_catalog(
    release_root: Path, prefixes: tuple[str, ...],
) -> SignedToolRecipeCatalog | None:
    if not (release_root / "release-manifest.json").is_file():
        return None
    trust_root = release_root.parents[1] / "trust"
    release = verify_installed_release(release_root, trust_root)
    key = _release_key(trust_root, release.signer_key_id)
    catalog = SignedToolRecipeCatalog(Ed25519RecipeSignatureVerifier({
        release.signer_key_id: key,
    }))
    count = 0
    total_bytes = 0
    names = set()
    for component in release.components:
        if component.kind is not ComponentKind.EXPERT:
            continue
        archive = release_root / component.kind.value / component.name
        try:
            source = tarfile.open(archive, "r")
        except tarfile.TarError:
            continue
        with source:
            for member in source.getmembers():
                if not member.name.startswith(prefixes):
                    continue
                if (
                    not member.isfile() or member.size <= 0
                    or member.size > 1_048_576 or member.name in names
                    or len(Path(member.name).parts) != 2
                    or Path(member.name).suffix != ".json"
                    or count >= 128 or total_bytes + member.size > 8_388_608
                ):
                    raise ValueError("installed engineering recipe member is unsafe")
                stream = source.extractfile(member)
                if stream is None:
                    raise ValueError("installed engineering recipe is unreadable")
                value = loads_document(stream.read().decode("utf-8", "strict"))
                if not isinstance(value, SignedToolRecipe):
                    raise TypeError("installed integration recipe has the wrong type")
                if value.signer_key_id != release.signer_key_id:
                    raise PermissionError("engineering recipe signer differs from release")
                catalog.admit(value)
                names.add(member.name)
                count += 1
                total_bytes += member.size
    return catalog if count else None


def _release_key(root: Path, key_id: str) -> Ed25519PublicKey:
    path = root / f"{key_id}.pem"
    if path.is_symlink() or not path.is_file():
        raise FileNotFoundError("integration recipe release key is unavailable")
    value = serialization.load_pem_public_key(path.read_bytes())
    if not isinstance(value, Ed25519PublicKey):
        raise TypeError("integration recipe release key is not Ed25519")
    return value
