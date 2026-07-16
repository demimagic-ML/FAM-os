"""Provider-neutral execution-plan graph contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from fam_os.core.contracts.version import CORE_CONTRACT_VERSION
from fam_os.routing.contracts import RouteDecision


class PlanStepKind(StrEnum):
    OBSERVE = "observe"
    INFERENCE = "inference"
    DETERMINISTIC_TOOL = "deterministic_tool"
    PREPARE_ACTION = "prepare_action"
    CONFIRM_ACTION = "confirm_action"
    EXECUTE_ACTION = "execute_action"
    VERIFY = "verify"
    FINALIZE = "finalize"


class StepOutcome(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DENIED = "denied"
    UNAVAILABLE = "unavailable"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class TerminalDisposition(StrEnum):
    RELEASE = "release"
    WITHHOLD = "withhold"
    FAIL = "fail"


@dataclass(frozen=True, slots=True)
class PlanStep:
    step_id: str
    kind: PlanStepKind
    description: str
    capability_ids: tuple[str, ...] = ()
    acceptance_ids: tuple[str, ...] = ()
    terminal_disposition: TerminalDisposition | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "step_id", _require_text(self.step_id, "step_id"))
        object.__setattr__(self, "description", _require_text(self.description, "description"))
        object.__setattr__(
            self,
            "capability_ids",
            _normalize_unique(self.capability_ids, "capability_ids"),
        )
        object.__setattr__(
            self,
            "acceptance_ids",
            _normalize_unique(self.acceptance_ids, "acceptance_ids"),
        )
        self._validate_kind()

    def _validate_kind(self) -> None:
        if self.kind is PlanStepKind.FINALIZE:
            if self.terminal_disposition is None:
                raise ValueError("finalize steps require a terminal disposition")
            if self.capability_ids or self.acceptance_ids:
                raise ValueError("finalize steps cannot execute capabilities or acceptance checks")
            return
        if self.terminal_disposition is not None:
            raise ValueError("only finalize steps may declare terminal disposition")
        capability_kinds = {
            PlanStepKind.OBSERVE,
            PlanStepKind.INFERENCE,
            PlanStepKind.DETERMINISTIC_TOOL,
            PlanStepKind.PREPARE_ACTION,
            PlanStepKind.CONFIRM_ACTION,
            PlanStepKind.EXECUTE_ACTION,
        }
        if self.kind in capability_kinds and not self.capability_ids:
            raise ValueError(f"{self.kind.value} steps require a capability")
        if self.kind in {PlanStepKind.EXECUTE_ACTION, PlanStepKind.VERIFY}:
            if not self.acceptance_ids:
                raise ValueError(f"{self.kind.value} steps require acceptance checks")


@dataclass(frozen=True, slots=True)
class PlanTransition:
    source_step_id: str
    outcome: StepOutcome
    target_step_id: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "source_step_id", _require_text(self.source_step_id, "source_step_id")
        )
        object.__setattr__(
            self, "target_step_id", _require_text(self.target_step_id, "target_step_id")
        )
        if self.source_step_id == self.target_step_id:
            raise ValueError("plan transitions cannot target their source")


@dataclass(frozen=True, slots=True)
class ExecutionPlan:
    plan_id: str
    request_id: str
    route: RouteDecision
    entry_step_id: str
    steps: tuple[PlanStep, ...]
    transitions: tuple[PlanTransition, ...]
    verification_required: bool = False
    contract_version: str = CORE_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for field_name in ("plan_id", "request_id", "entry_step_id", "contract_version"):
            object.__setattr__(
                self, field_name, _require_text(getattr(self, field_name), field_name)
            )
        if not self.steps:
            raise ValueError("execution plan requires steps")
        step_map = self._step_map()
        if self.entry_step_id not in step_map:
            raise ValueError("entry_step_id must reference a plan step")
        adjacency = self._validate_transitions(step_map)
        self._validate_graph(step_map, adjacency)
        self._validate_capability_coverage()

    def _step_map(self) -> dict[str, PlanStep]:
        step_map = {step.step_id: step for step in self.steps}
        if len(step_map) != len(self.steps):
            raise ValueError("plan step IDs must be unique")
        return step_map

    def _validate_transitions(
        self, step_map: dict[str, PlanStep]
    ) -> dict[str, tuple[str, ...]]:
        edges: dict[str, list[str]] = {step_id: [] for step_id in step_map}
        selectors: set[tuple[str, StepOutcome]] = set()
        for transition in self.transitions:
            if transition.source_step_id not in step_map or transition.target_step_id not in step_map:
                raise ValueError("plan transitions must reference known steps")
            selector = (transition.source_step_id, transition.outcome)
            if selector in selectors:
                raise ValueError("a step outcome must select at most one target")
            selectors.add(selector)
            edges[transition.source_step_id].append(transition.target_step_id)
        return {step_id: tuple(targets) for step_id, targets in edges.items()}

    def _validate_graph(
        self, step_map: dict[str, PlanStep], adjacency: dict[str, tuple[str, ...]]
    ) -> None:
        for step_id, step in step_map.items():
            targets = adjacency[step_id]
            if step.kind is PlanStepKind.FINALIZE and targets:
                raise ValueError("finalize steps cannot have outgoing transitions")
            if step.kind is not PlanStepKind.FINALIZE and not targets:
                raise ValueError("non-final steps require an outgoing transition")
        visited = _reachable(self.entry_step_id, adjacency)
        if visited != set(step_map):
            raise ValueError("every plan step must be reachable from the entry step")
        _require_acyclic(self.entry_step_id, adjacency)
        self._validate_release_predecessors(step_map)

    def _validate_release_predecessors(self, step_map: dict[str, PlanStep]) -> None:
        releases = {
            step.step_id
            for step in self.steps
            if step.terminal_disposition is TerminalDisposition.RELEASE
        }
        if not releases:
            raise ValueError("execution plan requires a release terminal")
        inbound_releases = {
            transition.target_step_id
            for transition in self.transitions
            if transition.target_step_id in releases
        }
        if inbound_releases != releases:
            raise ValueError("release terminals require an inbound transition")
        if not self.verification_required:
            return
        for transition in self.transitions:
            if transition.target_step_id not in releases:
                continue
            source = step_map[transition.source_step_id]
            if transition.outcome is not StepOutcome.SUCCEEDED or not source.acceptance_ids:
                raise ValueError("verified release terminals require successful accepted evidence")

    def _validate_capability_coverage(self) -> None:
        planned = {capability for step in self.steps for capability in step.capability_ids}
        routed = set(self.route.required_capabilities)
        if planned != routed:
            raise ValueError("execution plan must exactly cover routed capabilities")


def _reachable(start: str, adjacency: dict[str, tuple[str, ...]]) -> set[str]:
    pending = [start]
    visited: set[str] = set()
    while pending:
        current = pending.pop()
        if current in visited:
            continue
        visited.add(current)
        pending.extend(adjacency[current])
    return visited


def _require_acyclic(start: str, adjacency: dict[str, tuple[str, ...]]) -> None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(step_id: str) -> None:
        if step_id in visiting:
            raise ValueError("execution plan cannot contain cycles")
        if step_id in visited:
            return
        visiting.add(step_id)
        for target in adjacency[step_id]:
            visit(target)
        visiting.remove(step_id)
        visited.add(step_id)

    visit(start)


def _normalize_unique(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    normalized = tuple(_require_text(value, field_name) for value in values)
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{field_name} must be unique")
    return normalized


def _require_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized
