"""Immutable deterministic catalog of FAM client capabilities."""

from dataclasses import dataclass, field

from fam_os.core.ingress.contracts import IngressCapability


@dataclass(frozen=True, slots=True)
class InMemoryIngressCapabilityRegistry:
    capabilities: tuple[IngressCapability, ...]
    _by_id: dict[str, IngressCapability] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        by_id = {item.capability_id: item for item in self.capabilities}
        if len(by_id) != len(self.capabilities):
            raise ValueError("ingress capability IDs must be unique")
        object.__setattr__(self, "_by_id", by_id)

    def entries(self) -> tuple[IngressCapability, ...]:
        return tuple(sorted(self.capabilities, key=lambda item: item.capability_id))

    def get(self, capability_id: str) -> IngressCapability | None:
        return self._by_id.get(capability_id)
