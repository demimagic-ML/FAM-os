"""In-memory deterministic admission registries."""

from dataclasses import dataclass, field
from threading import Lock

from fam_os.core.admission.contracts import RequestAuthorityGrant


@dataclass(slots=True)
class InMemoryRequestAuthorityRegistry:
    grants: tuple[RequestAuthorityGrant, ...]
    _by_ref: dict[str, RequestAuthorityGrant] = field(init=False)

    def __post_init__(self) -> None:
        self._by_ref = {grant.authority_ref: grant for grant in self.grants}
        if len(self._by_ref) != len(self.grants):
            raise ValueError("authority references must be unique")

    def get(self, authority_ref: str) -> RequestAuthorityGrant | None:
        return self._by_ref.get(authority_ref)


@dataclass(slots=True)
class InMemoryRequestReplayRegistry:
    _request_ids: set[str] = field(default_factory=set)
    _lock: Lock = field(default_factory=Lock)

    def reserve(self, request_id: str) -> bool:
        with self._lock:
            if request_id in self._request_ids:
                return False
            self._request_ids.add(request_id)
            return True
