"""Ed25519 authority proof for privileged integration network requests."""

import base64
from dataclasses import replace

from cryptography.exceptions import InvalidSignature

from fam_os.core.engineering.integration_network import (
    integration_network_authority_payload,
)


class Ed25519IntegrationNetworkAuthority:
    def __init__(self, trusted_public_keys, *, signing_key_id=None, signing_key=None):
        self._trusted = dict(trusted_public_keys)
        self._signing_key_id, self._signing_key = signing_key_id, signing_key

    @property
    def key_id(self):
        if self._signing_key_id is None:
            raise PermissionError("integration network signing is unavailable")
        return self._signing_key_id

    def sign(self, draft):
        if self._signing_key is None or self._signing_key_id is None:
            raise PermissionError("integration network signing is unavailable")
        if draft.signer_key_id != self._signing_key_id:
            raise PermissionError("integration network signer identity is mismatched")
        signature = self._signing_key.sign(integration_network_authority_payload(draft))
        return replace(draft, signature_base64=base64.b64encode(signature).decode("ascii"))

    def verify(self, request) -> None:
        key = self._trusted.get(request.signer_key_id)
        if key is None:
            raise PermissionError("integration network signer is not trusted")
        try:
            signature = base64.b64decode(request.signature_base64, validate=True)
            key.verify(signature, integration_network_authority_payload(request))
        except (InvalidSignature, ValueError) as error:
            raise PermissionError("integration network authority signature is invalid") from error
