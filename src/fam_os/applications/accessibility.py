"""Provider-neutral bounded accessibility observation and action values."""

from dataclasses import dataclass
from datetime import datetime

from fam_os.applications.identifiers import require_identifier, require_text


@dataclass(frozen=True, slots=True)
class AccessibleObjectRef:
    process_id: int
    child_path: tuple[int, ...]
    fingerprint: str

    def __post_init__(self) -> None:
        if self.process_id <= 0 or any(index < 0 for index in self.child_path):
            raise ValueError("accessible object path is invalid")
        if len(self.fingerprint) != 64:
            raise ValueError("accessible object fingerprint must be SHA-256")

    @property
    def reference_id(self) -> str:
        return f"atspi:{self.process_id}:{'.'.join(map(str, self.child_path))}:{self.fingerprint[:16]}"


@dataclass(frozen=True, slots=True)
class AccessibleAction:
    name: str
    description: str | None = None
    key_binding: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", require_text(self.name, "action name"))
        for field_name in ("description", "key_binding"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, require_text(value, field_name))


@dataclass(frozen=True, slots=True)
class AccessibleNode:
    reference: AccessibleObjectRef
    parent_reference_id: str | None
    depth: int
    role: str
    name: str | None
    description: str | None
    states: tuple[str, ...]
    actions: tuple[AccessibleAction, ...]
    text: str | None = None
    protected: bool = False

    def __post_init__(self) -> None:
        if self.depth < 0:
            raise ValueError("accessible node depth cannot be negative")
        require_text(self.role, "accessible role")
        if self.parent_reference_id is not None:
            require_text(self.parent_reference_id, "parent_reference_id")
        if self.protected and any((self.name, self.description, self.text, self.actions)):
            raise ValueError("protected accessible nodes cannot expose content or actions")


@dataclass(frozen=True, slots=True)
class AccessibilitySnapshot:
    captured_at: datetime
    process_id: int
    nodes: tuple[AccessibleNode, ...]
    truncated: bool = False
    issue_code: str | None = None

    def __post_init__(self) -> None:
        if self.captured_at.tzinfo is None or self.process_id <= 0:
            raise ValueError("accessibility snapshot identity is invalid")
        references = tuple(item.reference.reference_id for item in self.nodes)
        if len(set(references)) != len(references):
            raise ValueError("accessibility node references must be unique")
        if self.issue_code is not None:
            require_identifier(self.issue_code, "accessibility issue code")


@dataclass(frozen=True, slots=True)
class AccessibilityActionProposal:
    operation_id: str
    reference: AccessibleObjectRef
    action_name: str
    action_index: int

    def __post_init__(self) -> None:
        require_identifier(self.operation_id, "operation_id")
        require_text(self.action_name, "action_name")
        if self.action_index < 0:
            raise ValueError("accessibility action index cannot be negative")


@dataclass(frozen=True, slots=True)
class AccessibilityActionEvidence:
    operation_id: str
    reference_id: str
    action_name: str
    invoked: bool
    before_fingerprint: str
    after_fingerprint: str | None = None

    def __post_init__(self) -> None:
        require_identifier(self.operation_id, "operation_id")
        require_text(self.reference_id, "reference_id")
        require_text(self.action_name, "action_name")
        if len(self.before_fingerprint) != 64:
            raise ValueError("before fingerprint must be SHA-256")
        if self.after_fingerprint is not None and len(self.after_fingerprint) != 64:
            raise ValueError("after fingerprint must be SHA-256")
