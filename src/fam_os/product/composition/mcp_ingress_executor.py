"""Authenticated MCP task execution through the production Core gateway."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from time import monotonic
from typing import Protocol
from uuid import uuid4

from fam_os.core.contracts import (
    FailureCategory,
    FailureComponent,
    FailureEnvelope,
    ResultStatus,
    RetryDisposition,
    TaskResult,
)
from fam_os.shell import ShellAskCommand, ShellCancelCommand


class McpTaskGateway(Protocol):
    def ask_as(self, command, principal_id: str, session_id: str): ...

    def snapshot(self, session_id: str): ...

    def cancel(self, command): ...


@dataclass(frozen=True, slots=True)
class ProductionMcpTaskExecutor:
    """Delegate an admitted MCP request without granting application authority."""

    gateway: McpTaskGateway
    timeout_seconds: float = 600.0
    poll_seconds: float = 0.02

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0 or self.poll_seconds <= 0:
            raise ValueError("MCP task execution timings must be positive")

    async def execute(self, admitted, parameters) -> TaskResult:
        capability_id = admitted.request.required_capabilities[0]
        internal_id = f"mcp-{uuid4()}"
        command = ShellAskCommand(
            internal_id, parameters["prompt"],
            verification_required=capability_id == "fam.ask.verified",
        )
        accepted = await asyncio.to_thread(
            self.gateway.ask_as, command,
            admitted.permission.principal_id, admitted.permission.session_id,
        )
        if accepted.result is not None:
            return _task_result(admitted.request.request_id, accepted)
        deadline = monotonic() + self.timeout_seconds
        latest = accepted
        while monotonic() < deadline:
            latest = await asyncio.to_thread(self.gateway.snapshot, accepted.session_id)
            if latest.result is not None:
                return _task_result(admitted.request.request_id, latest)
            await asyncio.sleep(self.poll_seconds)
        await asyncio.to_thread(
            self.gateway.cancel,
            ShellCancelCommand(accepted.session_id, latest.revision),
        )
        raise TimeoutError("MCP Core task exceeded its execution deadline")


def _task_result(request_id: str, snapshot) -> TaskResult:
    result = snapshot.result
    if result is None:
        raise ValueError("MCP task snapshot is not terminal")
    if result.status in {ResultStatus.COMPLETED, ResultStatus.VERIFIED}:
        return TaskResult(
            request_id, result.status, result.content, result.verified,
            plan_id=snapshot.session_id, evidence_ids=result.evidence_ids,
            assurance=result.assurance, citations=result.citations,
        )
    category = (
        FailureCategory.VERIFICATION_FAILED
        if result.status is ResultStatus.WITHHELD else FailureCategory.INTERNAL
    )
    code = (
        "mcp.task.withheld"
        if result.status is ResultStatus.WITHHELD else "mcp.task.failed"
    )
    reason = result.reason or "The FAM task did not complete."
    failure = FailureEnvelope(
        f"mcp-failure-{uuid4()}", category, code, reason,
        FailureComponent.CORE, RetryDisposition.WITH_BACKOFF,
        evidence_ids=result.evidence_ids,
    )
    return TaskResult(
        request_id, result.status, None, reason=reason,
        plan_id=snapshot.session_id, evidence_ids=result.evidence_ids,
        failure=failure,
    )
