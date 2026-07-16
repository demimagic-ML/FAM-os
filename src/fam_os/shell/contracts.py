"""Provider-neutral presentation contracts for the unprivileged FAM Shell."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from fam_os.core.contracts import ResultStatus


SHELL_CONTRACT_VERSION = "fam.shell/v1alpha1"


class ShellContextKind(StrEnum):
    APPLICATION = "application"
    FILE = "file"
    SELECTION = "selection"
    URI = "uri"


class ShellRunState(StrEnum):
    ACCEPTED = "accepted"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    CANCELLING = "cancelling"
    TERMINAL = "terminal"


class ShellStepState(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DENIED = "denied"
    CANCELLED = "cancelled"
    UNAVAILABLE = "unavailable"
    EXPIRED = "expired"


class ShellDecision(StrEnum):
    APPROVE = "approve"
    DENY = "deny"


@dataclass(frozen=True, slots=True)
class ShellContext:
    context_id: str
    kind: ShellContextKind
    resource_ref: str
    display_name: str
    capability_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _text(self.context_id, "context_id")
        if not isinstance(self.kind, ShellContextKind):
            raise ValueError("context kind is invalid")
        _text(self.resource_ref, "resource_ref")
        _text(self.display_name, "display_name")
        object.__setattr__(
            self, "capability_ids", _unique(self.capability_ids, "capability_ids")
        )


@dataclass(frozen=True, slots=True)
class ShellAskCommand:
    request_id: str
    prompt: str
    contexts: tuple[ShellContext, ...] = ()
    required_capabilities: tuple[str, ...] = ()
    verification_required: bool = False
    contract_version: str = SHELL_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _text(self.request_id, "request_id")
        _text(self.prompt, "prompt")
        if len(self.prompt) > 131_072 or len(self.contexts) > 64:
            raise ValueError("shell ask limits exceeded")
        if self.contract_version != SHELL_CONTRACT_VERSION:
            raise ValueError("unsupported shell contract version")
        if len({item.context_id for item in self.contexts}) != len(self.contexts):
            raise ValueError("context IDs must be unique")
        object.__setattr__(
            self, "required_capabilities",
            _unique(self.required_capabilities, "required_capabilities"),
        )


@dataclass(frozen=True, slots=True)
class ShellPlanStep:
    step_id: str
    kind: str
    description: str
    state: ShellStepState

    def __post_init__(self) -> None:
        _text(self.step_id, "step_id")
        _text(self.kind, "kind")
        _text(self.description, "description")
        if not isinstance(self.state, ShellStepState):
            raise ValueError("shell step state is invalid")


@dataclass(frozen=True, slots=True)
class ShellApprovalRequest:
    approval_id: str
    proposal_id: str
    capability_id: str
    summary: str
    expires_at: datetime
    reversible: bool

    def __post_init__(self) -> None:
        for name in ("approval_id", "proposal_id", "capability_id", "summary"):
            _text(getattr(self, name), name)
        if self.expires_at.tzinfo is None or self.expires_at.utcoffset() is None:
            raise ValueError("approval expiry must be timezone-aware")


@dataclass(frozen=True, slots=True)
class ShellResult:
    request_id: str
    status: ResultStatus
    content: str | None
    reason: str = ""
    verified: bool = False
    evidence_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _text(self.request_id, "request_id")
        if not isinstance(self.status, ResultStatus):
            raise ValueError("result status is invalid")
        object.__setattr__(
            self, "evidence_ids", _unique(self.evidence_ids, "evidence_ids")
        )
        successful = self.status in {ResultStatus.COMPLETED, ResultStatus.VERIFIED}
        if successful != bool(self.content):
            raise ValueError("result content must match successful status")
        if self.content is not None:
            _text(self.content, "content")
        if not successful:
            _text(self.reason, "reason")
        if self.verified != (self.status is ResultStatus.VERIFIED):
            raise ValueError("verified flag must match verified status")
        if self.verified and not self.evidence_ids:
            raise ValueError("verified result requires evidence")


@dataclass(frozen=True, slots=True)
class ShellSessionSnapshot:
    session_id: str
    request_id: str
    revision: int
    state: ShellRunState
    steps: tuple[ShellPlanStep, ...] = ()
    current_step_id: str | None = None
    message: str = ""
    approval: ShellApprovalRequest | None = None
    result: ShellResult | None = None
    contract_version: str = SHELL_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _text(self.session_id, "session_id")
        _text(self.request_id, "request_id")
        if self.revision < 0 or isinstance(self.revision, bool):
            raise ValueError("revision must be nonnegative")
        if not isinstance(self.state, ShellRunState):
            raise ValueError("shell run state is invalid")
        if self.contract_version != SHELL_CONTRACT_VERSION:
            raise ValueError("unsupported shell contract version")
        if self.message:
            _text(self.message, "message")
        self._validate_plan()
        self._validate_authority_surface()

    def _validate_plan(self) -> None:
        step_ids = tuple(item.step_id for item in self.steps)
        if len(set(step_ids)) != len(step_ids):
            raise ValueError("shell plan step IDs must be unique")
        if self.current_step_id is not None and self.current_step_id not in step_ids:
            raise ValueError("current step must belong to shell plan")
        active = tuple(item for item in self.steps if item.state is ShellStepState.ACTIVE)
        if len(active) > 1:
            raise ValueError("shell plan can have at most one active step")
        if active and active[0].step_id != self.current_step_id:
            raise ValueError("active step must be the current step")

    def _validate_authority_surface(self) -> None:
        waiting = self.state is ShellRunState.WAITING_APPROVAL
        if waiting != (self.approval is not None):
            raise ValueError("approval must match waiting state")
        terminal = self.state is ShellRunState.TERMINAL
        if terminal != (self.result is not None):
            raise ValueError("result must match terminal state")
        if self.result is not None and self.result.request_id != self.request_id:
            raise ValueError("result request must match shell session")
        if terminal and any(item.state is ShellStepState.ACTIVE for item in self.steps):
            raise ValueError("terminal shell sessions cannot have active steps")


@dataclass(frozen=True, slots=True)
class ShellDecisionCommand:
    session_id: str
    expected_revision: int
    approval_id: str
    decision: ShellDecision

    def __post_init__(self) -> None:
        _command(self.session_id, self.expected_revision)
        _text(self.approval_id, "approval_id")
        if not isinstance(self.decision, ShellDecision):
            raise ValueError("shell decision is invalid")


@dataclass(frozen=True, slots=True)
class ShellCancelCommand:
    session_id: str
    expected_revision: int

    def __post_init__(self) -> None:
        _command(self.session_id, self.expected_revision)


@dataclass(frozen=True, slots=True)
class ShellSnapshotQuery:
    session_id: str

    def __post_init__(self) -> None:
        _text(self.session_id, "session_id")


def _command(session_id, revision) -> None:
    _text(session_id, "session_id")
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 0:
        raise ValueError("expected revision must be nonnegative")


def _unique(values, name) -> tuple[str, ...]:
    normalized = tuple(_text(value, name) for value in values)
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{name} must be unique")
    return normalized


def _text(value, name) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise ValueError(f"{name} must be strict nonempty text")
    return value.strip()
