"""Exact memory-scope access matching."""

from dataclasses import dataclass

from fam_os.memory.manifest import MemoryScope

MEMORY_ACCESS_CONTRACT_VERSION = "fam.memory.access/v1alpha1"


@dataclass(frozen=True, slots=True)
class MemoryAccessContext:
    owner_id: str
    purpose_id: str
    application_id: str | None = None
    workspace_id: str | None = None
    session_id: str | None = None
    contract_version: str = MEMORY_ACCESS_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if not self.owner_id.strip() or not self.purpose_id.strip():
            raise ValueError("memory access owner and purpose are required")


def scope_allows(scope: MemoryScope, context: MemoryAccessContext) -> bool:
    return (
        scope.owner_id == context.owner_id
        and context.purpose_id in scope.purpose_ids
        and _optional_allows(scope.application_ids, context.application_id)
        and _optional_allows(scope.workspace_ids, context.workspace_id)
        and (scope.session_id is None or scope.session_id == context.session_id)
    )


def _optional_allows(allowed: tuple[str, ...], actual: str | None) -> bool:
    return not allowed or actual in allowed
