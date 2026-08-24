"""Iterative model agent over an authorized natural-engineering candidate."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from fam_os.core.agent import (
    AgentAuthorityProfile,
    AgentToolRegistry,
    AgentTurnOutcome,
    IterativeAgentSettings,
    IterativeModelAgent,
)
from fam_os.product.agent_command_tools import WorkspaceCommandTools
from fam_os.product.agent_turn_store import SQLiteAgentTurnStore
from fam_os.product.candidate_agent_tools import AuthorizedCandidateAgentTools


@dataclass(frozen=True, slots=True)
class NaturalEngineeringAgentResult:
    agent_outcome: AgentTurnOutcome
    applied_edits: tuple[object, ...]
    successful_verifications: tuple[str, ...]

    @property
    def producer_id(self) -> str:
        return self.agent_outcome.turn_id

    @property
    def summary(self) -> str:
        return self.agent_outcome.response.content


class NaturalEngineeringAgentService:
    def __init__(
        self, runtime, model_ref: str, database, loop, *, maximum_steps: int = 64,
    ) -> None:
        self._runtime = runtime
        self._model_ref = model_ref
        self._database = database
        self._loop = loop
        self._maximum_steps = maximum_steps

    def execute(
        self, owner_id: str, definition, preparation, *,
        session_id: str, principal_id: str, objective: str | None = None,
        turn_suffix: str = "implementation",
    ) -> NaturalEngineeringAgentResult:
        workspace = preparation.candidate.candidate_workspace
        registry = AgentToolRegistry()
        candidate_tools = AuthorizedCandidateAgentTools(
            self._loop, owner_id, definition.task.task_id, session_id,
            principal_id, definition, preparation,
            WorkspaceCommandTools(Path(workspace)),
        )
        candidate_tools.register(registry)
        thread_id = _thread_id(
            owner_id, session_id, preparation.candidate.owner_workspace,
        )
        turn_id = f"agent-turn-{definition.task.task_id}-{turn_suffix}"
        agent = IterativeModelAgent(
            self._runtime,
            IterativeAgentSettings(
                self._model_ref, maximum_steps=self._maximum_steps,
            ),
            registry,
            SQLiteAgentTurnStore(
                self._database, preparation.candidate.owner_workspace,
            ),
            completion_validator=lambda _results: (
                None
                if candidate_tools.applied_edits
                and candidate_tools.successful_verifications
                else (
                    "Implementation turns require an applied candidate edit and a "
                    "successful verify_command call. If a check already passed through "
                    "run_command, rerun that same check with verify_command so its "
                    "result becomes verification evidence. Do not stage or commit Git; "
                    "candidate approval and delivery happen after this turn."
                )
            ),
        )
        outcome = agent.run(
            thread_id=thread_id,
            turn_id=turn_id,
            objective=objective or definition.task.intent,
            profile=AgentAuthorityProfile.WORKSPACE,
            prior_context=_context(preparation),
        )
        if not candidate_tools.applied_edits:
            raise ValueError("engineering agent completed without candidate changes")
        if not candidate_tools.successful_verifications:
            raise ValueError("engineering agent completed without successful verification")
        return NaturalEngineeringAgentResult(
            outcome, tuple(candidate_tools.applied_edits),
            tuple(candidate_tools.successful_verifications),
        )

    def replay_verification(self, task_id: str, workspace: str) -> str:
        rows = self._database.fetchall(
            "SELECT calls.turn_id,calls.payload_json FROM agent_tool_events calls "
            "JOIN agent_tool_events results ON results.turn_id=calls.turn_id "
            "AND results.call_id=calls.call_id AND results.event_kind='result' "
            "WHERE calls.turn_id LIKE ? AND calls.tool_id='verify_command' "
            "AND calls.event_kind='call' AND json_extract(results.payload_json, "
            "'$.succeeded')=1 ORDER BY calls.event_id DESC LIMIT 1",
            (f"agent-turn-{task_id}-%",),
        )
        if len(rows) != 1:
            raise LookupError("agent verification command is unavailable")
        arguments = json.loads(rows[0][1]).get("arguments")
        if not isinstance(arguments, dict):
            raise ValueError("agent verification command arguments are invalid")
        output = WorkspaceCommandTools(Path(workspace)).run_command(arguments)
        if "status=completed" not in output or "exit_code=0" not in output:
            raise RuntimeError(output)
        return rows[0][0]


def _thread_id(owner_id: str, session_id: str, workspace: str) -> str:
    digest = hashlib.sha256(
        f"{owner_id}\0{session_id}\0{workspace}".encode(),
    ).hexdigest()[:32]
    return f"agent-thread-{digest}"


def _context(preparation) -> str:
    decisions = "\n".join(
        f"- {item.area.value}: {item.decision}"
        for item in preparation.proposal.decisions
    )
    relevant = "\n".join(
        f"- {path}" for path in preparation.analysis.relevant_paths
    )
    return (
        "Repository preparation guidance (advisory; inspect with tools):\n"
        f"{decisions}\nRelevant paths suggested by analysis:\n{relevant}\n"
        "You are editing an authorized staged candidate snapshot. It intentionally "
        "does not contain .git metadata. Use file and command tools against the "
        "candidate; Git observation tools report the unchanged owner repository."
    )
