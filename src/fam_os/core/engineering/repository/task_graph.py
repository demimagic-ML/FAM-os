"""Append-only bounded task graph and deterministic transition policy."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from fam_os.core.engineering._validation import aware, positive, text, texts
from fam_os.core.engineering.version import ENGINEERING_CONTRACT_VERSION


class EngineeringTaskStepKind(StrEnum):
    OBSERVE_REPOSITORY = "observe_repository"
    ANALYZE_REPOSITORY = "analyze_repository"
    TRACE_IMPLEMENTATION = "trace_implementation"
    SYNTHESIZE_ARCHITECTURE = "synthesize_architecture"
    CHECKPOINT = "checkpoint"
    TERMINAL = "terminal"


class EngineeringTaskStepState(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class EngineeringTaskGraphEventKind(StrEnum):
    STARTED = "started"
    STEP_COMPLETED = "step_completed"
    CHECKPOINT_REACHED = "checkpoint_reached"
    TERMINATED = "terminated"


@dataclass(frozen=True, slots=True)
class EngineeringTaskBudget:
    maximum_steps: int
    maximum_wall_seconds: int
    maximum_observation_bytes: int
    maximum_model_tokens: int

    def __post_init__(self) -> None:
        for name in (
            "maximum_steps", "maximum_wall_seconds", "maximum_observation_bytes",
            "maximum_model_tokens",
        ):
            positive(getattr(self, name), name)


@dataclass(frozen=True, slots=True)
class EngineeringTaskGraphStep:
    step_id: str
    kind: EngineeringTaskStepKind
    description: str
    depends_on: tuple[str, ...]
    checkpoint_after: bool

    def __post_init__(self) -> None:
        text(self.step_id, "step_id")
        text(self.description, "description")
        texts(self.depends_on, "depends_on")
        if self.step_id in self.depends_on:
            raise ValueError("task graph step cannot depend on itself")


@dataclass(frozen=True, slots=True)
class EngineeringTaskGraph:
    graph_id: str
    task_id: str
    created_at: datetime
    steps: tuple[EngineeringTaskGraphStep, ...]
    budget: EngineeringTaskBudget
    termination_conditions: tuple[str, ...]
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        text(self.graph_id, "graph_id")
        text(self.task_id, "task_id")
        aware(self.created_at, "created_at")
        if not self.steps or len(self.steps) > self.budget.maximum_steps:
            raise ValueError("task graph steps are empty or exceed budget")
        identities = tuple(item.step_id for item in self.steps)
        if len(set(identities)) != len(identities):
            raise ValueError("task graph step IDs must be unique")
        known: set[str] = set()
        for step in self.steps:
            if not set(step.depends_on) <= known:
                raise ValueError("task graph dependencies must point to earlier steps")
            known.add(step.step_id)
        if self.steps[-1].kind is not EngineeringTaskStepKind.TERMINAL:
            raise ValueError("task graph must end in an explicit terminal step")
        texts(self.termination_conditions, "termination_conditions")
        if not self.termination_conditions:
            raise ValueError("task graph requires termination conditions")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("engineering task graph version is unsupported")


@dataclass(frozen=True, slots=True)
class EngineeringTaskGraphEvent:
    event_id: str
    graph_id: str
    task_id: str
    sequence: int
    occurred_at: datetime
    kind: EngineeringTaskGraphEventKind
    step_id: str
    step_state: EngineeringTaskStepState
    remaining_wall_seconds: int
    remaining_observation_bytes: int
    remaining_model_tokens: int
    evidence_ids: tuple[str, ...]
    reason_code: str
    checkpoint_required: bool
    terminal: bool
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in ("event_id", "graph_id", "task_id", "step_id", "reason_code"):
            text(getattr(self, name), name)
        positive(self.sequence, "sequence", allow_zero=True)
        aware(self.occurred_at, "occurred_at")
        for name in (
            "remaining_wall_seconds", "remaining_observation_bytes",
            "remaining_model_tokens",
        ):
            positive(getattr(self, name), name, allow_zero=True)
        texts(self.evidence_ids, "evidence_ids")
        if self.terminal != (self.kind is EngineeringTaskGraphEventKind.TERMINATED):
            raise ValueError("task graph terminal flag must match event kind")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("engineering task graph event version is unsupported")


class EngineeringTaskGraphService:
    def __init__(self, repository) -> None:
        self._repository = repository

    def append(self, graph: EngineeringTaskGraph, event: EngineeringTaskGraphEvent) -> bool:
        history = self._repository.history(graph.graph_id)
        self._validate(graph, history, event)
        expected = -1 if not history else history[-1].sequence
        return self._repository.append(expected, event)

    @staticmethod
    def _validate(graph, history, event) -> None:
        expected_sequence = len(history)
        if (
            event.graph_id != graph.graph_id
            or event.task_id != graph.task_id
            or event.sequence != expected_sequence
        ):
            raise ValueError("task graph event identity or sequence is invalid")
        step_map = {item.step_id: item for item in graph.steps}
        step = step_map.get(event.step_id)
        if step is None:
            raise ValueError("task graph event references an unknown step")
        if history and history[-1].terminal:
            raise ValueError("terminal task graph cannot advance")
        if not history and (
            event.remaining_wall_seconds > graph.budget.maximum_wall_seconds
            or event.remaining_observation_bytes > graph.budget.maximum_observation_bytes
            or event.remaining_model_tokens > graph.budget.maximum_model_tokens
        ):
            raise ValueError("task graph initial event exceeds declared budget")
        if history:
            previous = history[-1]
            for name in (
                "remaining_wall_seconds", "remaining_observation_bytes",
                "remaining_model_tokens",
            ):
                if getattr(event, name) > getattr(previous, name):
                    raise ValueError("task graph remaining budget cannot increase")
        elif event.kind is not EngineeringTaskGraphEventKind.STARTED:
            raise ValueError("task graph history must begin with started")
        states = {item.step_id: item.step_state for item in history}
        if event.kind is EngineeringTaskGraphEventKind.STARTED:
            if history or event.step_id != graph.steps[0].step_id:
                raise ValueError("task graph started event must activate the first step")
            if event.step_state is not EngineeringTaskStepState.ACTIVE:
                raise ValueError("task graph started event must be active")
        else:
            if states.get(event.step_id) in {
                EngineeringTaskStepState.SUCCEEDED,
                EngineeringTaskStepState.FAILED,
                EngineeringTaskStepState.CANCELLED,
            }:
                raise ValueError("task graph step already reached a terminal state")
            if any(
                states.get(dependency) is not EngineeringTaskStepState.SUCCEEDED
                for dependency in step.depends_on
            ):
                raise ValueError("task graph step dependencies are incomplete")
        if event.kind is EngineeringTaskGraphEventKind.CHECKPOINT_REACHED:
            if event.step_state is not EngineeringTaskStepState.SUCCEEDED:
                raise ValueError("task graph checkpoint requires a succeeded step")
        if event.checkpoint_required != step.checkpoint_after:
            raise ValueError("task graph event checkpoint does not match step policy")
        if event.terminal and step.kind is not EngineeringTaskStepKind.TERMINAL:
            raise ValueError("only terminal task graph step may terminate")
