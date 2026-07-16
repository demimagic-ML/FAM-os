"""Read-only product visibility contracts for FAM Console."""

from dataclasses import asdict, dataclass
from datetime import datetime


CONSOLE_CONTRACT_VERSION = "fam.console/v1alpha1"
REQUIRED_SECTIONS = (
    "resources", "experts", "permissions", "memory", "audit", "recovery",
)


@dataclass(frozen=True, slots=True)
class ConsoleItem:
    item_id: str
    label: str
    value: str
    status: str
    detail: str = ""

    def __post_init__(self) -> None:
        if not all((self.item_id, self.label, self.value, self.status)):
            raise ValueError("console item fields must not be empty")
        if self.status not in {"healthy", "attention", "inactive", "unavailable"}:
            raise ValueError("console item status is invalid")


@dataclass(frozen=True, slots=True)
class ConsoleSection:
    section_id: str
    title: str
    items: tuple[ConsoleItem, ...]

    def __post_init__(self) -> None:
        if self.section_id not in REQUIRED_SECTIONS or not self.title:
            raise ValueError("console section is invalid")
        identities = tuple(item.item_id for item in self.items)
        if len(set(identities)) != len(identities):
            raise ValueError("console item IDs must be unique within a section")


@dataclass(frozen=True, slots=True)
class ConsoleSnapshot:
    observed_at: datetime
    owner_uid: int
    release_id: str
    sections: tuple[ConsoleSection, ...]
    recovery_mode: bool
    contract_version: str = CONSOLE_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None or self.owner_uid < 0 or not self.release_id:
            raise ValueError("console snapshot identity is invalid")
        if tuple(section.section_id for section in self.sections) != REQUIRED_SECTIONS:
            raise ValueError("console snapshot must contain every ordered section")
        if self.contract_version != CONSOLE_CONTRACT_VERSION:
            raise ValueError("unsupported console contract version")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
