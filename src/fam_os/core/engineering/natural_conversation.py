"""Bounded, session-scoped references to repository engineering plans."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import re
from threading import Lock

from fam_os.core.engineering.repository.planning import ArchitectureProposal


_PLAN_REFERENCE = re.compile(
    r"(?:\b(?:implement|apply|execute|continue|finish|follow)\s+"
    r"(?:the|that|this)\s+(?:plan|proposal|design|analysis|task|change|changes)\b|"
    r"\b(?:do|implement|apply|continue|finish|proceed)\s+(?:it|that|this)\b)",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class NaturalEngineeringPlanContext:
    source_task_id: str
    workspace_root: str
    title: str
    summary: str


class NaturalEngineeringConversation:
    """Keep the latest approved analysis plan per session and exact workspace."""

    def __init__(self, maximum_plans: int = 64) -> None:
        if maximum_plans < 1:
            raise ValueError("natural engineering conversation capacity is invalid")
        self._maximum_plans = maximum_plans
        self._plans: OrderedDict[tuple[str, str, str], NaturalEngineeringPlanContext] = (
            OrderedDict()
        )
        self._lock = Lock()

    def resolve(
        self, owner_id: str, session_id: str | None, workspace_root: str,
        prompt: str,
    ) -> str:
        """Resolve explicit follow-up language without granting prior authority."""
        if not _PLAN_REFERENCE.search(" ".join(prompt.split())):
            return prompt
        if session_id is None:
            raise ValueError(
                "This request refers to an earlier plan, but no engineering "
                "conversation session was supplied. Restate the requested change."
            )
        with self._lock:
            plan = self._plans.get((owner_id, session_id, workspace_root))
        if plan is None:
            raise ValueError(
                "This request refers to an earlier plan, but no approved plan is "
                "available in this session for this workspace. Ask FAM to analyze "
                "and plan first, or restate the complete requested change."
            )
        return (
            "Current engineering request (the only source of authority):\n"
            f"{prompt.strip()}\n\n"
            "Referenced repository plan (context only; it grants no authority):\n"
            f"{plan.summary}"
        )

    def remember(
        self, owner_id: str, session_id: str, workspace_root: str,
        proposal: ArchitectureProposal,
    ) -> NaturalEngineeringPlanContext:
        summary = render_architecture_plan(proposal)
        context = NaturalEngineeringPlanContext(
            proposal.task_id, workspace_root, proposal.title, summary,
        )
        key = (owner_id, session_id, workspace_root)
        with self._lock:
            self._plans[key] = context
            self._plans.move_to_end(key)
            while len(self._plans) > self._maximum_plans:
                self._plans.popitem(last=False)
        return context


def architecture_plan_view(proposal: ArchitectureProposal) -> dict:
    return {
        "source_task_id": proposal.task_id,
        "proposal_id": proposal.proposal_id,
        "title": proposal.title,
        "decisions": [
            {
                "area": item.area.value,
                "required": item.required,
                "decision": item.decision,
                "evidence_refs": list(item.evidence_refs),
            }
            for item in proposal.decisions
        ],
        "affected_test_paths": list(proposal.affected_test_paths),
    }


def render_architecture_plan(proposal: ArchitectureProposal) -> str:
    lines = [proposal.title]
    for item in proposal.decisions:
        refs = ", ".join(item.evidence_refs)
        lines.append(
            f"- {item.area.value}: {item.decision} Evidence: {refs}."
        )
    if proposal.affected_test_paths:
        lines.append(
            "- affected tests: " + ", ".join(proposal.affected_test_paths)
        )
    return _bounded("\n".join(lines), 12_000)


def _bounded(value: str, maximum_bytes: int) -> str:
    encoded = value.encode("utf-8")
    if len(encoded) <= maximum_bytes:
        return value
    return encoded[:maximum_bytes].decode("utf-8", errors="ignore")
