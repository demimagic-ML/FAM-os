"""Core-owned Shell gateway for bounded unverified local chat inference."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from uuid import uuid4

from fam_os.core.contracts import ResultStatus
from fam_os.core.ports.inference import (
    InferenceMessage, InferenceRequest, InferenceRuntime, MessageRole,
)
from fam_os.shell import (
    ShellCancelCommand, ShellDecisionCommand, ShellPlanStep, ShellResult,
    ShellRunState, ShellSessionSnapshot, ShellStepState,
)


@dataclass(slots=True)
class _ChatSession:
    request_id: str
    prompt: str
    snapshot: ShellSessionSnapshot


class LocalInferenceShellGateway:
    """Expose local text generation without granting tools or action authority."""

    def __init__(
        self, runtime: InferenceRuntime, model_ref: str,
        context_tokens: int = 8192, max_output_tokens: int = 512,
    ) -> None:
        if not model_ref.strip() or min(context_tokens, max_output_tokens) <= 0:
            raise ValueError("local chat model and token limits are required")
        self._runtime = runtime
        self._model_ref = model_ref
        self._context_tokens = context_tokens
        self._max_output_tokens = max_output_tokens
        self._sessions: dict[str, _ChatSession] = {}
        self._lock = Lock()

    def ask(self, command) -> ShellSessionSnapshot:
        if command.contexts or command.required_capabilities:
            raise ValueError("local chat does not accept application authority")
        if command.verification_required:
            raise ValueError("unverified chat cannot satisfy verification-required requests")
        session_id = f"chat-{uuid4()}"
        snapshot = ShellSessionSnapshot(
            session_id, command.request_id, 0, ShellRunState.ACCEPTED,
            (_step(ShellStepState.PENDING),), message=f"Queued for {self._model_ref}",
        )
        with self._lock:
            self._sessions[session_id] = _ChatSession(
                command.request_id, command.prompt, snapshot,
            )
        return snapshot

    def snapshot(self, session_id: str) -> ShellSessionSnapshot:
        with self._lock:
            session = self._require(session_id)
            if session.snapshot.state is ShellRunState.TERMINAL:
                return session.snapshot
            session.snapshot = self._run(session_id, session)
            return session.snapshot

    def decide(self, command: ShellDecisionCommand) -> ShellSessionSnapshot:
        raise ValueError("local chat never requests action approval")

    def cancel(self, command: ShellCancelCommand) -> ShellSessionSnapshot:
        with self._lock:
            session = self._require(command.session_id)
            if command.expected_revision != session.snapshot.revision:
                raise ValueError("chat cancellation revision is stale")
            if session.snapshot.state is ShellRunState.TERMINAL:
                return session.snapshot
            session.snapshot = _terminal(
                command.session_id, session.request_id, ResultStatus.WITHHELD,
                None, "Cancelled before inference", 1,
            )
            return session.snapshot

    def _run(self, session_id: str, session: _ChatSession) -> ShellSessionSnapshot:
        request = InferenceRequest(
            self._model_ref,
            (InferenceMessage(MessageRole.SYSTEM, _SYSTEM_PROMPT),
             InferenceMessage(MessageRole.USER, session.prompt)),
            self._context_tokens, self._max_output_tokens, temperature=0.2,
        )
        try:
            response = self._runtime.chat(request)
            return _terminal(
                session_id, session.request_id, ResultStatus.COMPLETED,
                response.content, "", 1,
            )
        except Exception:
            return _terminal(
                session_id, session.request_id, ResultStatus.FAILED,
                None, "Local inference is unavailable", 1,
            )

    def _require(self, session_id: str) -> _ChatSession:
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError("local chat session does not exist")
        return session


_SYSTEM_PROMPT = (
    "You are FAM_OS, a local assistant. Answer the user's text request directly. "
    "Do not claim to inspect files, use applications, execute tools, or verify facts."
)


def _step(state: ShellStepState) -> ShellPlanStep:
    return ShellPlanStep("local-inference", "model_inference", "Generate locally", state)


def _terminal(session_id, request_id, status, content, reason, revision):
    return ShellSessionSnapshot(
        session_id, request_id, revision, ShellRunState.TERMINAL,
        (_step(ShellStepState.SUCCEEDED if content else ShellStepState.FAILED),),
        "local-inference", "Local inference completed" if content else reason,
        result=ShellResult(request_id, status, content, reason),
    )
