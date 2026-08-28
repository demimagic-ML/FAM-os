"""Durable provider usage telemetry and Omarchy agent-panel projection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sqlite3
from threading import RLock
import time
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class AgentUsageEvent:
    event_id: str
    observed_at: str
    provider: str
    model_ref: str
    input_tokens: int
    output_tokens: int
    wall_seconds: float


class AgentUsageRepository:
    """Append real inference metrics and aggregate them without loading a log."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = RLock()
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._initialize()

    def add(
        self, provider: str, model_ref: str, input_tokens: int,
        output_tokens: int, wall_seconds: float,
    ) -> AgentUsageEvent:
        event = AgentUsageEvent(
            str(uuid4()), datetime.now(timezone.utc).isoformat(),
            provider.strip() or "unknown", model_ref.strip() or "unknown",
            max(0, int(input_tokens)), max(0, int(output_tokens)),
            max(0.0, float(wall_seconds)),
        )
        with self._lock, self._connect() as connection:
            connection.execute(
                "INSERT INTO agent_usage VALUES (?,?,?,?,?,?,?)",
                (
                    event.event_id, event.observed_at, event.provider,
                    event.model_ref, event.input_tokens, event.output_tokens,
                    event.wall_seconds,
                ),
            )
        return event

    def omarchy_record(
        self, now: datetime | None = None, *, goals: dict[str, int] | None = None,
    ) -> dict[str, object]:
        current = now or datetime.now(timezone.utc)
        local_today = current.astimezone().date()
        days = [local_today - timedelta(days=offset) for offset in range(6, -1, -1)]
        recent = {day.isoformat(): 0 for day in days}
        today_models: dict[str, int] = {}
        model_usage: dict[str, dict[str, int]] = {}
        provider_usage: dict[str, dict[str, int | float]] = {}
        active_dates: set[str] = set()
        today_prompts = today_total = total_prompts = 0
        active_seconds = 0.0
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                "SELECT observed_at,provider,model_ref,input_tokens,output_tokens,wall_seconds "
                "FROM agent_usage ORDER BY observed_at"
            ).fetchall()
        for observed_at, provider, model_ref, input_tokens, output_tokens, wall_seconds in rows:
            try:
                observed = datetime.fromisoformat(str(observed_at).replace("Z", "+00:00"))
                day = observed.astimezone().date().isoformat()
            except ValueError:
                continue
            input_count = max(0, int(input_tokens))
            output_count = max(0, int(output_tokens))
            total = input_count + output_count
            duration = max(0.0, float(wall_seconds))
            active_seconds += duration
            total_prompts += 1
            active_dates.add(day)
            bucket = model_usage.setdefault(str(model_ref), {
                "inputTokens": 0,
                "outputTokens": 0,
                "cacheReadInputTokens": 0,
                "cacheCreationInputTokens": 0,
            })
            bucket["inputTokens"] += input_count
            bucket["outputTokens"] += output_count
            provider_bucket = provider_usage.setdefault(str(provider), {
                "inputTokens": 0, "outputTokens": 0,
                "totalTokens": 0, "activeSeconds": 0.0,
            })
            provider_bucket["inputTokens"] += input_count
            provider_bucket["outputTokens"] += output_count
            provider_bucket["totalTokens"] += total
            provider_bucket["activeSeconds"] += duration
            if day in recent:
                recent[day] += total
            if day == local_today.isoformat():
                today_prompts += 1
                today_total += total
                today_models[str(model_ref)] = today_models.get(str(model_ref), 0) + total
        goal_usage = goals or {"total": 0, "active": 0, "completed": 0, "failed": 0}
        hosted = sum(
            int(value["totalTokens"]) for key, value in provider_usage.items()
            if key.casefold() not in {"ollama", "lm-studio", "local"}
        )
        local = sum(int(value["totalTokens"]) for value in provider_usage.values()) - hosted
        return {
            "schemaVersion": 1,
            "id": "fam-os",
            "name": "FAM_OS",
            "updatedAt": current.isoformat(),
            "ready": True,
            "hasLocalStats": True,
            "todayPrompts": today_prompts,
            "todaySessions": today_prompts,
            "todayTotalTokens": today_total,
            "todayTokensByModel": today_models,
            "recentDays": [
                {"date": day.isoformat(), "messageCount": recent[day.isoformat()]}
                for day in days
            ],
            "totalPrompts": total_prompts,
            "totalSessions": total_prompts,
            "activeDays": len(active_dates),
            "activeDates": sorted(active_dates),
            "modelUsage": model_usage,
            "providerUsage": provider_usage,
            "taskCount": total_prompts,
            "goalCount": int(goal_usage.get("total", 0)),
            "goals": goal_usage,
            "activeSeconds": round(active_seconds, 3),
            "cacheUsage": {
                "readInputTokens": 0,
                "creationInputTokens": 0,
                "available": False,
            },
            "inferenceLocation": {
                "localTokens": local,
                "hostedTokens": hosted,
            },
            "limits": [],
            "tierLabel": "Local",
            "usageStatusText": "Local FAM_OS inference",
            "authHelpText": "",
        }

    def _initialize(self) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS agent_usage ("
                "event_id TEXT PRIMARY KEY, observed_at TEXT NOT NULL, "
                "provider TEXT NOT NULL, model_ref TEXT NOT NULL, "
                "input_tokens INTEGER NOT NULL, output_tokens INTEGER NOT NULL, "
                "wall_seconds REAL NOT NULL)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS agent_usage_observed_at "
                "ON agent_usage(observed_at)"
            )
        os.chmod(self.path, 0o600)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=5)


class UsageTelemetryRuntime:
    """Transparent runtime decorator that records provider-returned token metrics."""

    def __init__(
        self, runtime, repository: AgentUsageRepository, provider: str,
        model_ref: str | None = None,
    ) -> None:
        self._runtime = runtime
        self._repository = repository
        self._provider = provider
        self._model_ref = model_ref

    def chat(self, request):
        response = self._runtime.chat(request)
        metrics = response.metrics
        self._repository.add(
            self._provider, metrics.model_ref, metrics.prompt_tokens,
            metrics.output_tokens, metrics.wall_seconds,
        )
        return response

    def execute_engineering_agent(self, prompt, workspace, *, writable: bool):
        started = time.monotonic()
        result = self._runtime.execute_engineering_agent(
            prompt, workspace, writable=writable,
        )
        self._repository.add(
            self._provider, self._model_ref or self._provider,
            result.input_tokens, result.output_tokens,
            time.monotonic() - started,
        )
        return result

    def __getattr__(self, name: str):
        return getattr(self._runtime, name)


def print_omarchy_usage(state_root: Path, output: Path | None = None) -> int:
    record = AgentUsageRepository(
        state_root / "state/agent-usage.sqlite3",
    ).omarchy_record(goals=_goal_usage(state_root / "state/engineering-goals.sqlite3"))
    payload = json.dumps(record, separators=(",", ":"), sort_keys=True) + "\n"
    if output is None:
        print(payload, end="")
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(output.suffix + ".tmp")
        temporary.write_text(payload, encoding="utf-8")
        os.chmod(temporary, 0o600)
        os.replace(temporary, output)
    return 0


def _goal_usage(path: Path) -> dict[str, int]:
    counts = {"total": 0, "active": 0, "completed": 0, "failed": 0}
    if not path.is_file():
        return counts
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=2) as connection:
            rows = connection.execute(
                "SELECT status,COUNT(*) FROM engineering_goals GROUP BY status"
            ).fetchall()
    except sqlite3.Error:
        return counts
    active = {
        "draft", "queued", "running", "retry_wait", "pause_requested",
        "paused", "cancel_requested", "waiting_approval",
    }
    for status, value in rows:
        amount = max(0, int(value))
        counts["total"] += amount
        if status in active:
            counts["active"] += amount
        elif status == "completed":
            counts["completed"] += amount
        elif status in {"failed", "cancelled"}:
            counts["failed"] += amount
    return counts
