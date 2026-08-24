"""Fail-closed repair for a terminal plan with unfinished execution state."""

from __future__ import annotations

from typing import Protocol, cast

from fam_os.core.lifecycle import PlanInstanceSnapshot
from fam_os.core.production.contracts import (
    InferenceExecutionRecord,
    InferenceExecutionState,
)
from fam_os.core.production.execution_state import terminal_execution


class _InferenceExecutions(Protocol):
    def get(self, instance_id: str) -> InferenceExecutionRecord | None: ...

    def replace(
        self, expected_revision: int, value: InferenceExecutionRecord,
    ) -> bool: ...


class _Repositories(Protocol):
    inference_executions: _InferenceExecutions


def reconcile_terminal_execution(
    repositories: _Repositories,
    record: InferenceExecutionRecord,
    snapshot: PlanInstanceSnapshot,
    *,
    failure_code: str,
) -> InferenceExecutionRecord:
    """Commit the missing execution terminal state after the worker has stopped."""
    if not snapshot.terminal:
        raise ValueError("only a terminal plan can reconcile terminal execution")
    current = repositories.inference_executions.get(record.instance_id)
    if current is None:
        raise KeyError("inference execution does not exist")
    if current.state is InferenceExecutionState.TERMINAL:
        return current
    try:
        return cast(InferenceExecutionRecord, terminal_execution(  # type: ignore[no-untyped-call]
            repositories, current, failure_code=failure_code,
        ))
    except RuntimeError:
        latest = repositories.inference_executions.get(record.instance_id)
        if latest is not None and latest.state is InferenceExecutionState.TERMINAL:
            return latest
        raise
