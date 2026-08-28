"""Iterative model agent over an authorized natural-engineering candidate."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from fam_os.core.agent import (
    AgentAuthorityProfile, AgentFinalResponse,
    AgentToolEffect,
    AgentToolRegistry,
    AgentTurnOutcome,
    IterativeAgentSettings,
    IterativeModelAgent,
)
from fam_os.core.engineering import EngineeringAuthority
from fam_os.core.ports.inference import (
    InferenceMessage, InferenceRequest, MessageRole,
)
from fam_os.product.agent_command_tools import WorkspaceCommandTools
from fam_os.product.agent_application_tools import ApplicationAgentTools
from fam_os.product.agent_host_command_tools import HostCommandTools
from fam_os.product.agent_turn_store import SQLiteAgentTurnStore
from fam_os.product.agent_workspace_tools import WorkspaceAgentTools
from fam_os.product.candidate_agent_tools import AuthorizedCandidateAgentTools
from fam_os.product.application_test_tools import ApplicationTestTools
from fam_os.product.native_application_test_tools import NativeApplicationTestTools


@dataclass(frozen=True, slots=True)
class NaturalEngineeringAgentResult:
    agent_outcome: AgentTurnOutcome
    applied_edits: tuple[object, ...]
    successful_verifications: tuple[str, ...]
    application_test: dict[str, object] | None = None

    @property
    def producer_id(self) -> str:
        return self.agent_outcome.turn_id

    @property
    def summary(self) -> str:
        return self.agent_outcome.response.content


class NaturalEngineeringAgentService:
    def __init__(
        self, runtime, model_ref: str, database, loop, *, maximum_steps: int = 64,
        fallback_model_ref: str | None = None,
        application_provider=lambda: None,
    ) -> None:
        self._runtime = runtime
        self._model_ref = model_ref
        self._database = database
        self._loop = loop
        self._maximum_steps = maximum_steps
        self._fallback_model_ref = fallback_model_ref
        self._application_provider = application_provider

    def execute(
        self, owner_id: str, definition, preparation, *,
        session_id: str, principal_id: str, objective: str | None = None,
        turn_suffix: str = "implementation", maximum_steps: int | None = None,
    ) -> NaturalEngineeringAgentResult:
        workspace = preparation.candidate.candidate_workspace
        profile = (
            AgentAuthorityProfile.FULL_OS
            if EngineeringAuthority.HOST_ADMIN in definition.task.authorities
            else AgentAuthorityProfile.APPLICATION_TEST
            if EngineeringAuthority.APPLICATION_TEST in definition.task.authorities
            else AgentAuthorityProfile.WORKSPACE
        )
        registry = AgentToolRegistry()
        candidate_tools = AuthorizedCandidateAgentTools(
            self._loop, owner_id, definition.task.task_id, session_id,
            principal_id, definition, preparation,
            (
                HostCommandTools(Path(workspace))
                if profile is AgentAuthorityProfile.FULL_OS else
                WorkspaceCommandTools(Path(workspace))
            ),
            command_effect=(
                AgentToolEffect.OS_WRITE
                if profile is AgentAuthorityProfile.FULL_OS else
                AgentToolEffect.COMMAND
            ),
        )
        turn_store = SQLiteAgentTurnStore(
            self._database, preparation.candidate.owner_workspace,
        )
        prior_edits = tuple(
            item for item in self._loop.candidate_edits(
                owner_id, definition.task.task_id,
            )
            if getattr(getattr(item, "status", None), "value", None) == "applied"
        )
        restored = turn_store.restore_turn(
            _thread_id(
                owner_id, session_id, preparation.candidate.owner_workspace,
            ),
            f"agent-turn-{definition.task.task_id}-{turn_suffix}",
        )
        prior_verifications = tuple(
            result.output for call, result in restored
            if result.succeeded and (
                call.tool_id == "verify_command"
                or bool((result.postcondition or {}).get("verified"))
            )
        )
        candidate_tools.restore(prior_edits, prior_verifications)
        candidate_tools.register(registry)
        ApplicationAgentTools(
            self._application_provider, owner_id, profile=profile,
        ).register(registry)
        application_tools = None
        native_application_tools = None
        if profile in {
            AgentAuthorityProfile.APPLICATION_TEST,
            AgentAuthorityProfile.FULL_OS,
        }:
            application_tools = ApplicationTestTools(
                Path(workspace), objective=objective or definition.task.intent,
            )
            application_tools.register(registry)
            native_application_tools = NativeApplicationTestTools(Path(workspace))
            native_application_tools.register(registry)
        thread_id = _thread_id(
            owner_id, session_id, preparation.candidate.owner_workspace,
        )
        turn_id = f"agent-turn-{definition.task.task_id}-{turn_suffix}"
        native_executor = getattr(self._runtime, "execute_engineering_agent", None)
        if callable(native_executor):
            before = candidate_tools.capture_workspace()
            try:
                native = native_executor(
                    _native_agent_prompt(
                        objective or definition.task.intent,
                        _context(preparation), profile,
                    ),
                    Path(workspace), writable=True,
                )
                candidate_tools.reconcile_workspace(
                    before, summary="Codex native agent changed candidate files.",
                )
            except Exception:
                try:
                    candidate_tools.reconcile_workspace(
                        before,
                        summary="Codex native agent preserved interrupted work.",
                    )
                except Exception:
                    candidate_tools.discard_workspace_changes(before)
                if application_tools is not None:
                    application_tools.cleanup(interrupted=True)
                if native_application_tools is not None:
                    native_application_tools.cleanup()
                raise
            candidate_tools.record_native_verifications(native.successful_commands)
            application_test = None
            if (
                not candidate_tools.applied_edits
                and profile is AgentAuthorityProfile.APPLICATION_TEST
                and candidate_tools.successful_verifications
            ):
                application_test = {
                    "status": "passed", "provider": "codex-native",
                    "successful_commands": list(native.successful_commands),
                }
            elif not candidate_tools.applied_edits:
                raise ValueError(
                    "Codex engineering agent completed without candidate changes"
                )
            if not candidate_tools.successful_verifications:
                raise ValueError(
                    "Codex engineering agent completed without successful command evidence"
                )
            if application_tools is not None:
                application_tools.cleanup(interrupted=False)
            if native_application_tools is not None:
                native_application_tools.cleanup()
            return NaturalEngineeringAgentResult(
                AgentTurnOutcome(
                    thread_id, turn_id, AgentFinalResponse(native.content), (),
                    native.model_steps,
                ),
                tuple(candidate_tools.applied_edits),
                tuple(candidate_tools.successful_verifications),
                application_test,
            )
        agent = IterativeModelAgent(
            self._runtime,
            _agent_settings(
                self._model_ref, maximum_steps or self._maximum_steps,
                objective or definition.task.intent,
                fallback_model_ref=self._fallback_model_ref,
            ),
            registry,
            turn_store,
            completion_validator=lambda _results: (
                None if (
                    application_tools is not None
                    and application_tools.all_checks_passed
                ) or (
                    native_application_tools is not None
                    and native_application_tools.all_checks_passed
                ) or (
                    candidate_tools.applied_edits
                    and candidate_tools.successful_verifications
                ) else (
                    "Implementation turns require an applied candidate edit and a "
                    "successful semantic postcondition or verify_command call. "
                    "Application-test turns require a passed app_assert receipt for "
                    "every harness-owned check. If a "
                    "check already passed through "
                    "run_command, rerun that same check with verify_command so its "
                    "result becomes verification evidence. Do not stage or commit Git; "
                    "candidate approval and delivery happen after this turn."
                )
            ),
        )
        completed = False
        try:
            outcome = agent.run(
                thread_id=thread_id,
                turn_id=turn_id,
                objective=objective or definition.task.intent,
                profile=profile,
                prior_context=_context(preparation),
            )
            completed = True
        finally:
            if application_tools is not None:
                application_tools.cleanup(interrupted=not completed)
            if native_application_tools is not None:
                native_application_tools.cleanup()
        if not candidate_tools.applied_edits and application_tools is None:
            raise ValueError("engineering agent completed without candidate changes")
        if (
            not candidate_tools.successful_verifications
            and not (
                application_tools is not None
                and application_tools.all_checks_passed
            )
            and not (
                native_application_tools is not None
                and native_application_tools.all_checks_passed
            )
        ):
            raise ValueError("engineering agent completed without successful verification")
        successful_verifications = list(candidate_tools.successful_verifications)
        if application_tools is not None and application_tools.all_checks_passed:
            successful_verifications.append(
                "application-test:all-harness-checks-passed"
            )
        if (
            native_application_tools is not None
            and native_application_tools.all_checks_passed
        ):
            successful_verifications.append(
                "native-application-test:all-harness-checks-passed"
            )
        return NaturalEngineeringAgentResult(
            outcome, tuple(candidate_tools.applied_edits),
            tuple(successful_verifications),
            (
                native_application_tools.summary
                if native_application_tools is not None
                and native_application_tools.summary is not None
                else None if application_tools is None else application_tools.summary
            ),
        )

    def answer(
        self, owner_id: str, definition, preparation, *, session_id: str,
    ) -> AgentTurnOutcome:
        workspace = preparation.candidate.owner_workspace
        registry = AgentToolRegistry()
        WorkspaceAgentTools(Path(workspace)).register(registry)
        ApplicationAgentTools(
            self._application_provider, owner_id,
            profile=AgentAuthorityProfile.ASK,
        ).register(registry)
        thread_id = _thread_id(owner_id, session_id, workspace)
        native_executor = getattr(self._runtime, "execute_engineering_agent", None)
        if callable(native_executor):
            native = native_executor(
                _native_answer_prompt(definition.task.intent, _context(preparation)),
                Path(workspace), writable=False,
            )
            return AgentTurnOutcome(
                thread_id, f"agent-turn-{definition.task.task_id}-ask",
                AgentFinalResponse(native.content), (), native.model_steps,
            )
        agent = IterativeModelAgent(
            self._runtime,
            _agent_settings(
                self._model_ref, self._maximum_steps, definition.task.intent,
                fallback_model_ref=self._fallback_model_ref,
            ),
            registry,
            SQLiteAgentTurnStore(self._database, workspace),
            completion_validator=lambda results: (
                None if any(
                    item.succeeded and item.tool_id in {
                        "read_file", "search_text", "list_directory",
                    }
                    for item in results
                ) else (
                    "A repository answer requires successful source evidence from "
                    "read_file, search_text, or list_directory. Git status alone is not "
                    "evidence for implementation behavior. Paths are relative files or "
                    "directories, not globs; use '.' to search the whole workspace."
                )
            ),
            completion_reviewer=self._review_answer,
        )
        return agent.run(
            thread_id=thread_id,
            turn_id=f"agent-turn-{definition.task.task_id}-ask",
            objective=definition.task.intent,
            profile=AgentAuthorityProfile.ASK,
            prior_context=_context(preparation),
        )

    def _review_answer(self, objective, response, results) -> str | None:
        evidence = []
        used = 0
        for item in results:
            output = item.output[:8_000]
            size = len(output.encode("utf-8"))
            if used + size > 24_000:
                break
            evidence.append({
                "tool": item.tool_id,
                "succeeded": item.succeeded,
                "output": output,
            })
            used += size
        review = self._runtime.chat(InferenceRequest(
            model_ref=self._model_ref,
            messages=(
                InferenceMessage(
                    MessageRole.SYSTEM,
                    "Review a local agent answer against its exact objective and tool "
                    "evidence. Accept only when it directly answers the question and its "
                    "claims follow from successful evidence. Reject unrelated environment "
                    "diagnoses, conclusions based on failed or unknown tools, and answers "
                    "that omit requested directory or file facts present in evidence. "
                    "Return only JSON: {\"accepted\":true|false,\"reason\":\"...\"}.",
                ),
                InferenceMessage(MessageRole.USER, json.dumps({
                    "objective": objective,
                    "proposed_answer": response.content,
                    "tool_evidence": evidence,
                }, sort_keys=True, separators=(",", ":"))),
            ),
            context_tokens=32_768,
            max_output_tokens=512,
            keep_alive="30m",
            json_output=True,
            temperature=0.0,
            seed=43,
        ))
        try:
            decision = json.loads(review.content)
        except (json.JSONDecodeError, TypeError):
            return "The grounding reviewer could not validate this answer; resynthesize it."
        if (
            not isinstance(decision, dict)
            or set(decision) != {"accepted", "reason"}
            or not isinstance(decision.get("accepted"), bool)
            or not isinstance(decision.get("reason"), str)
        ):
            return "The grounding reviewer returned an invalid decision; resynthesize it."
        if decision["accepted"]:
            return None
        return f"Grounding review rejected the answer: {decision['reason'][:1_000]}"

    def replay_verification(
        self, task_id: str, workspace: str, *, full_os: bool = False,
        candidate_workspace: str | None = None,
    ) -> str:
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
        overlays = ()
        if candidate_workspace is not None:
            candidate_root = Path(candidate_workspace).resolve(strict=True)
            arguments = _postapply_verification_arguments(arguments)
            overlays = _candidate_toolchain_overlays(
                arguments, Path(workspace).resolve(strict=True), candidate_root,
            )
        command_tools = (
            HostCommandTools(Path(workspace))
            if full_os else WorkspaceCommandTools(
                Path(workspace), read_only_overlays=overlays,
            )
        )
        output = command_tools.run_command(arguments)
        if "status=completed" not in output or "exit_code=0" not in output:
            raise RuntimeError(output)
        return rows[0][0]


    def thread(
        self, owner_id: str, session_id: str, workspace: str,
    ) -> dict[str, object]:
        store = SQLiteAgentTurnStore(self._database, workspace)
        thread_id = _thread_id(owner_id, session_id, workspace)
        return store.thread(thread_id) or {
            "thread_id": thread_id,
            "workspace_root": workspace,
            "authority_profile": AgentAuthorityProfile.WORKSPACE.value,
            "turns": [],
        }

    def control_thread(
        self, owner_id: str, session_id: str, workspace: str,
        kind: str, content: str,
    ) -> dict[str, object]:
        store = SQLiteAgentTurnStore(self._database, workspace)
        thread_id = _thread_id(owner_id, session_id, workspace)
        store.request_control(thread_id, kind, content)
        return {"thread_id": thread_id, "accepted": True, "control_kind": kind}


def _candidate_toolchain_overlays(
    arguments: dict[str, object], owner_root: Path, candidate_root: Path,
) -> tuple[tuple[Path, Path], ...]:
    command = arguments.get("command")
    if not isinstance(command, list):
        return ()
    overlays = []
    for value in command:
        if isinstance(value, str) and "node_modules/" in value:
            prefix = value.split("node_modules/", 1)[0]
            relative = Path(prefix) / "node_modules"
            source, destination = candidate_root / relative, owner_root / relative
            if source.is_dir():
                overlays.append((source, destination))
    return tuple(dict.fromkeys(overlays))


def _postapply_verification_arguments(
    arguments: dict[str, object],
) -> dict[str, object]:
    command = arguments.get("command")
    if (
        not isinstance(command, list)
        or not any(
            isinstance(value, str) and "vitest" in value.casefold()
            for value in command
        )
        or "--no-cache" in command
    ):
        return arguments
    return {**arguments, "command": [*command, "--no-cache"]}


def _thread_id(owner_id: str, session_id: str, workspace: str) -> str:
    digest = hashlib.sha256(
        f"{owner_id}\0{session_id}\0{workspace}".encode(),
    ).hexdigest()[:32]
    return f"agent-thread-{digest}"


def _native_agent_prompt(
    objective: str, prior_context: str, profile: AgentAuthorityProfile,
) -> str:
    return (
        "Work as the primary coding agent in the workspace you were given. "
        "Inspect the real project, implement the complete objective, run relevant "
        "tests, builds, and runtime checks, diagnose failures, and keep correcting "
        "the work until it is genuinely complete. Use your native filesystem, shell, "
        "search, planning, web, and other available coding tools. Do not merely "
        "propose a patch. Do not stage, commit, push, or modify Git metadata; FAM owns "
        "final verification and delivery. Keep filesystem changes inside the current "
        f"candidate workspace. Authority profile: {profile.value}.\n\n"
        f"Objective:\n{objective}\n\nFAM context:\n{prior_context}"
    )


def _native_answer_prompt(objective: str, prior_context: str) -> str:
    return (
        "Inspect the workspace directly with your native read, search, and reasoning "
        "tools, then answer from concrete source evidence. This is a read-only turn: "
        "do not edit files, install dependencies, or run mutating commands.\n\n"
        f"Question:\n{objective}\n\nFAM context:\n{prior_context}"
    )


def _agent_settings(
    model_ref: str, maximum_steps: int, objective: str = "",
    *, fallback_model_ref: str | None = None,
) -> IterativeAgentSettings:
    normalized = model_ref.casefold()
    small_local = any(
        marker in normalized for marker in (":7b", "-7b", ":3b", ":1.7b")
    )
    qwen38 = "qwen3.8" in normalized
    return IterativeAgentSettings(
        model_ref, maximum_steps=maximum_steps,
        context_tokens=(
            8_192 if small_local else 65_536 if qwen38 else 32_768
        ),
        maximum_output_tokens=(
            2_048 if small_local else 8_192 if qwen38 else 4_096
        ),
        keep_alive="30m",
        fallback_model_ref=fallback_model_ref,
    )


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
