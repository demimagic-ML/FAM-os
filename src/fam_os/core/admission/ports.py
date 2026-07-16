"""Provider-neutral authority and replay ports for Core admission."""

from typing import Protocol

from fam_os.core.admission.contracts import RequestAuthorityGrant


class RequestAuthorityRegistry(Protocol):
    def get(self, authority_ref: str) -> RequestAuthorityGrant | None: ...


class RequestReplayRegistry(Protocol):
    def reserve(self, request_id: str) -> bool: ...
