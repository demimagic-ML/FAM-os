"""Typed Core boundary for policy-authorized grounded retrieval."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Protocol

from fam_os.core.production.contracts import ModelIntent
from fam_os.verification import VerificationDeclaration


GROUNDED_INTENTS = frozenset({
    ModelIntent.GROUNDED_QUESTION,
    ModelIntent.RETRIEVAL,
})


@dataclass(frozen=True, slots=True)
class GroundingAccessContext:
    application_id: str
    session_id: str
    workspace_id: str | None = None

    def __post_init__(self) -> None:
        for name in ("application_id", "session_id"):
            value = getattr(self, name)
            if not value.strip() or "\x00" in value:
                raise ValueError(f"grounding {name} must be strict nonempty text")
        if self.workspace_id is not None and (
            not self.workspace_id.strip() or "\x00" in self.workspace_id
        ):
            raise ValueError("grounding workspace_id must be strict nonempty text")


class GroundedRetrievalUnavailable(ValueError):
    """A grounded intent cannot safely proceed without authorized sources."""


class GroundedRetrievalPort(Protocol):
    def declaration_for(
        self,
        request_id: str,
        prompt: str,
        intent: ModelIntent,
        access: GroundingAccessContext,
    ) -> VerificationDeclaration: ...


class GroundedRequestPreparer:
    def __init__(self, retrieval: GroundedRetrievalPort | None) -> None:
        self._retrieval = retrieval

    def prepare(self, command, intent: ModelIntent, access: GroundingAccessContext):
        if self._retrieval is None or intent not in GROUNDED_INTENTS:
            return command, None
        declaration = self._retrieval.declaration_for(
            command.request_id, command.prompt, intent, access,
        )
        return replace(command, verification_required=True), declaration
