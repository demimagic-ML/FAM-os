"""Typed evidence for installed intent, model selection, and inference."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from fam_os.fabric.remote_execution import RemoteExecutionPlan


INFERENCE_EXECUTION_VERSION = "fam.core.inference-execution/v1alpha1"


class ModelIntent(StrEnum):
    CONVERSATION = "conversation"
    GROUNDED_QUESTION = "grounded_question"
    READ_ONLY_TASK = "read_only_task"
    APPLICATION_MUTATION = "application_mutation"
    CODE = "code"
    MATH = "math"
    RETRIEVAL = "retrieval"
    MEDIA = "media"
    ADMINISTRATION = "administration"


class AssuranceLevel(StrEnum):
    UNVERIFIED = "unverified"
    GROUNDED = "grounded"
    VERIFIED = "verified"


class InferenceExecutionState(StrEnum):
    PREPARED = "prepared"
    RUNNING = "running"
    CANDIDATE_READY = "candidate_ready"
    TERMINAL = "terminal"


@dataclass(frozen=True, slots=True)
class RuntimeModelEntry:
    model_ref: str
    tier: str
    intents: tuple[ModelIntent, ...]
    estimated_resident_bytes: int
    max_context_tokens: int
    manifest_sha256: str
    verifier_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _text(self.model_ref, "model_ref")
        if self.tier not in {"economical", "specialist", "escalation", "embedding"}:
            raise ValueError("runtime model tier is invalid")
        if not self.intents or len(set(self.intents)) != len(self.intents):
            raise ValueError("runtime model intents must be nonempty and unique")
        if self.estimated_resident_bytes <= 0 or self.max_context_tokens <= 0:
            raise ValueError("runtime model resource values must be positive")
        if len(self.manifest_sha256) != 64:
            raise ValueError("runtime model manifest digest must be SHA-256")
        if any(character not in "0123456789abcdef" for character in self.manifest_sha256):
            raise ValueError("runtime model manifest digest must be lowercase hex")
        _unique(self.verifier_ids, "verifier_ids")


@dataclass(frozen=True, slots=True)
class RuntimeModelSelection:
    selection_id: str
    request_id: str
    intent: ModelIntent
    model_ref: str
    tier: str
    estimated_resident_bytes: int
    available_host_bytes: int
    available_vram_bytes: int
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("selection_id", "request_id", "model_ref", "tier"):
            _text(getattr(self, name), name)
        if min(
            self.estimated_resident_bytes,
            self.available_host_bytes,
            self.available_vram_bytes,
        ) < 0:
            raise ValueError("model selection resources cannot be negative")
        _unique(self.reason_codes, "reason_codes", require=True)


@dataclass(frozen=True, slots=True)
class InferenceExecutionRecord:
    instance_id: str
    request_id: str
    intent: ModelIntent
    selection: RuntimeModelSelection
    state: InferenceExecutionState
    revision: int
    candidate_id: str | None = None
    assurance: AssuranceLevel = AssuranceLevel.UNVERIFIED
    failure_code: str | None = None
    verifier_feedback: str = ""
    contract_version: str = INFERENCE_EXECUTION_VERSION
    remote_plan: RemoteExecutionPlan | None = None
    remote_attempt_consumed: bool = False

    def __post_init__(self) -> None:
        _text(self.instance_id, "instance_id")
        _text(self.request_id, "request_id")
        if self.selection.request_id != self.request_id:
            raise ValueError("model selection request does not match execution")
        if self.remote_plan is not None and (
            self.remote_plan.instance_id != self.instance_id
            or self.remote_plan.request_id != self.request_id
        ):
            raise ValueError("remote plan does not match inference execution")
        if not isinstance(self.remote_attempt_consumed, bool):
            raise TypeError("remote attempt consumption state is invalid")
        if self.remote_attempt_consumed and self.remote_plan is None:
            raise ValueError("remote attempt cannot be consumed without a remote plan")
        if (
            self.remote_plan is not None
            and not self.remote_attempt_consumed
            and self.selection.model_ref != self.remote_plan.model_ref
        ):
            raise ValueError("pending remote plan differs from model selection")
        if self.revision < 0 or isinstance(self.revision, bool):
            raise ValueError("inference execution revision must be nonnegative")
        if self.contract_version != INFERENCE_EXECUTION_VERSION:
            raise ValueError("inference execution contract version is unsupported")
        if self.state is InferenceExecutionState.CANDIDATE_READY and not self.candidate_id:
            raise ValueError("candidate-ready execution requires candidate evidence")
        if self.state is InferenceExecutionState.TERMINAL:
            if not self.candidate_id and not self.failure_code:
                raise ValueError("terminal execution requires candidate or failure evidence")
        elif self.failure_code is not None:
            raise ValueError("only terminal inference may carry a failure code")
        if len(self.verifier_feedback) > 16_000 or "\x00" in self.verifier_feedback:
            raise ValueError("verifier feedback exceeds its safe disclosure bound")


def _text(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise ValueError(f"{name} must be strict nonempty text")


def _unique(values: tuple[str, ...], name: str, *, require: bool = False) -> None:
    if require and not values:
        raise ValueError(f"{name} must not be empty")
    if len(set(values)) != len(values) or any(not value.strip() for value in values):
        raise ValueError(f"{name} must contain unique nonempty values")
