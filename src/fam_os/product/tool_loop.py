"""Reusable bounded, checkpointed execution loop over typed product tools."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable


@dataclass(frozen=True, slots=True)
class ToolStep:
    step_id: str
    tool_id: str
    arguments: dict[str, object]
    maximum_attempts: int = 1

    def __post_init__(self) -> None:
        if not self.step_id or not self.tool_id or not 1 <= self.maximum_attempts <= 3:
            raise ValueError("tool step is invalid")


@dataclass(frozen=True, slots=True)
class ToolResult:
    output: dict[str, object]
    artifacts: tuple[object, ...] = ()


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Callable[[dict[str, object]], ToolResult]] = {}

    def register(self, tool_id: str, tool: Callable[[dict[str, object]], ToolResult]) -> None:
        if not tool_id or tool_id in self._tools:
            raise ValueError("tool registration is invalid or duplicate")
        self._tools[tool_id] = tool

    def invoke(self, tool_id: str, arguments: dict[str, object]) -> ToolResult:
        tool = self._tools.get(tool_id)
        if tool is None:
            raise KeyError(f"unknown tool: {tool_id}")
        result = tool(dict(arguments))
        if not isinstance(result, ToolResult):
            raise TypeError("tool returned an invalid result")
        return result

    def ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._tools))


class ToolLoopRepository:
    def __init__(self, database) -> None:
        self._database = database

    def start(self, task_id: str, step: ToolStep, attempt: int) -> None:
        self._database.execute(
            "INSERT INTO useful_task_steps(task_id,step_id,tool_id,arguments_json,attempt,"
            "status,started_at) VALUES(?,?,?,?,?,'running',?)",
            (task_id, step.step_id, step.tool_id, json.dumps(step.arguments, sort_keys=True), attempt, _now()),
        )

    def finish(self, task_id: str, step_id: str, attempt: int, result: ToolResult) -> None:
        self._database.execute(
            "UPDATE useful_task_steps SET status='completed',output_json=?,completed_at=? "
            "WHERE task_id=? AND step_id=? AND attempt=?",
            (json.dumps(result.output, sort_keys=True), _now(), task_id, step_id, attempt),
        )

    def fail(self, task_id: str, step_id: str, attempt: int, error: str) -> None:
        self._database.execute(
            "UPDATE useful_task_steps SET status='failed',error=?,completed_at=? "
            "WHERE task_id=? AND step_id=? AND attempt=?",
            (error[:500], _now(), task_id, step_id, attempt),
        )

    def timeline(self, task_id: str) -> tuple[dict[str, object], ...]:
        rows = self._database.fetchall(
            "SELECT step_id,tool_id,arguments_json,attempt,status,output_json,error,"
            "started_at,completed_at FROM useful_task_steps WHERE task_id=? "
            "ORDER BY rowid",
            (task_id,),
        )
        return tuple({
            "step_id": row[0], "tool_id": row[1], "arguments": json.loads(row[2]),
            "attempt": row[3], "status": row[4],
            "output": None if row[5] is None else json.loads(row[5]),
            "error": row[6], "started_at": row[7], "completed_at": row[8],
        } for row in rows)


class BoundedToolLoop:
    def __init__(self, registry: ToolRegistry, repository: ToolLoopRepository) -> None:
        self._registry = registry
        self._repository = repository

    def run(self, task_id: str, steps: tuple[ToolStep, ...]) -> tuple[ToolResult, ...]:
        if not 1 <= len(steps) <= 64:
            raise ValueError("tool loop requires between one and 64 steps")
        if len({item.step_id for item in steps}) != len(steps):
            raise ValueError("tool loop step ids must be unique")
        results = []
        for step in steps:
            last_error: Exception | None = None
            for attempt in range(1, step.maximum_attempts + 1):
                self._repository.start(task_id, step, attempt)
                try:
                    result = self._registry.invoke(step.tool_id, step.arguments)
                except Exception as error:
                    last_error = error
                    self._repository.fail(task_id, step.step_id, attempt, str(error))
                    continue
                self._repository.finish(task_id, step.step_id, attempt, result)
                results.append(result)
                break
            else:
                detail = "unknown failure" if last_error is None else str(last_error)
                raise RuntimeError(
                    f"tool step {step.step_id} failed after "
                    f"{step.maximum_attempts} attempt(s): {detail}"
                ) from last_error
        return tuple(results)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
