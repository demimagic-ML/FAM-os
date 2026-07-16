"""Caller context and injected authorization port for supervisor admission."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Protocol

from fam_os.supervisor.boundary import SupervisorCapability


_IDENTITY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,255}$")


@dataclass(frozen=True, slots=True)
class SupervisorCallContext:
    request_id: str
    principal_id: str
    session_id: str
    authority_ref: str

    def __post_init__(self) -> None:
        values = (self.request_id, self.principal_id, self.session_id, self.authority_ref)
        if any(not _IDENTITY.fullmatch(value) for value in values):
            raise ValueError("supervisor call context identity is invalid")


class SupervisorAuthorizer(Protocol):
    def require(
        self,
        context: SupervisorCallContext,
        capability: SupervisorCapability,
        service_id: str,
    ) -> None: ...
