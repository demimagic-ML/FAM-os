"""Input contract for one FAM_OS task."""

from __future__ import annotations

from dataclasses import dataclass
import re

from fam_os.core.contracts.version import CORE_CONTRACT_VERSION


_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,255}$")
_MAX_PROMPT_CHARACTERS = 131_072
_MAX_REQUIRED_CAPABILITIES = 64


@dataclass(frozen=True, slots=True)
class TaskRequest:
    """A provider-independent request accepted by FAM Core."""

    request_id: str
    prompt: str
    required_capabilities: tuple[str, ...] = ()
    verification_required: bool = False
    contract_version: str = CORE_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if not _IDENTIFIER.fullmatch(self.request_id):
            raise ValueError("request_id is invalid")
        if (
            not self.prompt.strip() or "\0" in self.prompt
            or len(self.prompt) > _MAX_PROMPT_CHARACTERS
        ):
            raise ValueError("prompt must not be empty")
        if self.contract_version != CORE_CONTRACT_VERSION:
            raise ValueError("unsupported contract_version")
        normalized = tuple(capability.strip() for capability in self.required_capabilities)
        if len(normalized) > _MAX_REQUIRED_CAPABILITIES:
            raise ValueError("too many required capabilities")
        if any(not _IDENTIFIER.fullmatch(capability) for capability in normalized):
            raise ValueError("required capability is invalid")
        if len(set(normalized)) != len(normalized):
            raise ValueError("required capabilities must be unique")
        object.__setattr__(self, "required_capabilities", normalized)
