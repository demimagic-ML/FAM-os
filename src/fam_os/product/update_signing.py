"""Canonical Ed25519 signing and verification for release manifests."""

import base64
import json

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from fam_os.product.update_contracts import SignedReleaseManifest


def sign_manifest(release_id, components, key_id, private_key):
    payload = canonical_payload(release_id, components, key_id)
    return SignedReleaseManifest(
        release_id, components, key_id,
        base64.b64encode(private_key.sign(payload)).decode(),
    )


def verify_manifest(manifest: SignedReleaseManifest, public_key: Ed25519PublicKey) -> None:
    signature = base64.b64decode(manifest.signature_base64, validate=True)
    public_key.verify(signature, canonical_payload(
        manifest.release_id, manifest.components, manifest.signer_key_id,
    ))


def canonical_payload(release_id, components, key_id):
    document = {
        "release_id": release_id,
        "signer_key_id": key_id,
        "components": [
            {"kind": item.kind.value, "name": item.name,
             "source_path": item.source_path, "sha256": item.sha256}
            for item in components
        ],
    }
    return json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
