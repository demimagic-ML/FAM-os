"""Signed atomic local Expert Factory publication."""

import base64
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

FACTORY_RELEASE_CONTRACT_VERSION = "fam.factory.release/v1alpha1"


@dataclass(frozen=True, slots=True)
class PublishedExpertPackage:
    package_id: str
    manifest_sha256: str
    signature_base64: str
    publisher_key_id: str
    publication_path: str
    signature_verified: bool
    contract_version: str = FACTORY_RELEASE_CONTRACT_VERSION


def sign_and_publish(package_id, manifest, key_id, private_key, directory):
    payload = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    signature = private_key.sign(payload)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{package_id}.json"
    temporary = target.with_suffix(".tmp")
    document = {"manifest": manifest, "signature": base64.b64encode(signature).decode(),
                "publisher_key_id": key_id}
    temporary.write_text(json.dumps(document, sort_keys=True) + "\n")
    os.chmod(temporary, 0o600)
    temporary.replace(target)
    private_key.public_key().verify(signature, payload)
    return PublishedExpertPackage(package_id, hashlib.sha256(payload).hexdigest(),
                                  document["signature"], key_id, str(target), True)


def verify_published(path: Path, public_key: Ed25519PublicKey):
    document = json.loads(path.read_text())
    payload = json.dumps(document["manifest"], sort_keys=True, separators=(",", ":")).encode()
    public_key.verify(base64.b64decode(document["signature"]), payload)
    return document["manifest"]
