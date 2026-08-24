"""Persistent manual, interval, webhook, and file-change workflow automation."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from typing import Any


TRIGGER_TYPES = {"manual", "interval", "webhook", "file_changed"}
RUN_MODES = {"single", "restart", "queued", "parallel"}


class AutomationService:
    def __init__(self, database, tasks, *, poll_seconds: float = 15.0) -> None:
        self._database = database
        self._tasks = tasks
        self._poll_seconds = poll_seconds
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._running: set[str] = set()
        self._lock = threading.RLock()

    def start(self) -> None:
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, daemon=True, name="fam-automations")
            self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None

    def create(self, document: dict) -> dict[str, object]:
        name = _text(document, "name")
        request = document.get("request")
        trigger = document.get("trigger")
        condition = document.get("condition", {})
        mode = document.get("run_mode", "single")
        if not isinstance(request, dict) or not isinstance(trigger, dict) or not isinstance(condition, dict):
            raise ValueError("automation request, trigger, and condition must be objects")
        if trigger.get("type") not in TRIGGER_TYPES or mode not in RUN_MODES:
            raise ValueError("automation trigger or run mode is unsupported")
        _validate_trigger(trigger)
        identifier, now = str(uuid4()), _now()
        state = _initial_state(trigger)
        self._database.execute(
            "INSERT INTO useful_automations(automation_id,name,request_json,trigger_json,"
            "condition_json,run_mode,enabled,trigger_state_json,created_at,updated_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                identifier, name, json.dumps(request, sort_keys=True),
                json.dumps(trigger, sort_keys=True), json.dumps(condition, sort_keys=True),
                mode, int(document.get("enabled", True)), json.dumps(state, sort_keys=True), now, now,
            ),
        )
        return self.inspect(identifier)

    def list(self) -> dict[str, list[dict[str, object]]]:
        rows = self._database.fetchall(
            "SELECT automation_id,name,request_json,trigger_json,condition_json,run_mode,"
            "enabled,created_at,updated_at,last_run_at,last_task_id,last_status "
            "FROM useful_automations ORDER BY created_at DESC",
        )
        return {"automations": [_automation(row) for row in rows]}

    def inspect(self, automation_id: str) -> dict[str, object]:
        for item in self.list()["automations"]:
            if item["automation_id"] == automation_id:
                return item
        raise KeyError("automation was not found")

    def run_now(self, automation_id: str) -> dict[str, object]:
        record = self.inspect(automation_id)
        return self._execute(record)

    def runs(self, automation_id: str) -> dict[str, object]:
        self.inspect(automation_id)
        rows = self._database.fetchall(
            "SELECT run_id,status,started_at,completed_at,task_id,error FROM "
            "useful_automation_runs WHERE automation_id=? ORDER BY started_at DESC LIMIT 100",
            (automation_id,),
        )
        return {"automation_id": automation_id, "runs": [{
            "run_id": row[0], "status": row[1], "started_at": row[2],
            "completed_at": row[3], "task_id": row[4], "error": row[5],
        } for row in rows]}

    def notifications(self) -> dict[str, object]:
        rows = self._database.fetchall(
            "SELECT notification_id,kind,title,message,task_id,created_at,read_at "
            "FROM useful_notifications ORDER BY created_at DESC LIMIT 100",
        )
        return {"notifications": [{
            "notification_id": row[0], "kind": row[1], "title": row[2],
            "message": row[3], "task_id": row[4], "created_at": row[5],
            "read_at": row[6],
        } for row in rows]}

    def tick(self) -> tuple[dict[str, object], ...]:
        results = []
        for record in self.list()["automations"]:
            if record["enabled"] and self._triggered(record):
                results.append(self._execute(record))
        return tuple(results)

    def _triggered(self, record: dict[str, Any]) -> bool:
        trigger = record["trigger"]
        if trigger["type"] in {"manual", "webhook"}:
            return False
        state_row = self._database.fetchone(
            "SELECT trigger_state_json FROM useful_automations WHERE automation_id=?",
            (record["automation_id"],),
        )
        state = json.loads(state_row[0])
        if trigger["type"] == "interval":
            last = state.get("last_checked_epoch", 0.0)
            now = datetime.now(timezone.utc).timestamp()
            if now - last < trigger["seconds"]:
                return False
            self._update_state(record["automation_id"], {"last_checked_epoch": now})
            return True
        path = Path(trigger["path"])
        observed = path.stat().st_mtime_ns if path.exists() else None
        changed = state.get("mtime_ns") != observed
        self._update_state(record["automation_id"], {"mtime_ns": observed})
        return changed and _condition_matches(record["condition"], path)

    def _execute(self, record: dict[str, Any]) -> dict[str, object]:
        identifier = record["automation_id"]
        with self._lock:
            if identifier in self._running and record["run_mode"] == "single":
                return {"automation_id": identifier, "status": "skipped_running"}
            self._running.add(identifier)
        run_id, started = str(uuid4()), _now()
        self._database.execute(
            "INSERT INTO useful_automation_runs(run_id,automation_id,status,started_at) "
            "VALUES(?,?,'running',?)", (run_id, identifier, started),
        )
        try:
            task = self._tasks.run(record["request"])
            now = _now()
            self._database.execute(
                "UPDATE useful_automations SET last_run_at=?,last_task_id=?,last_status=?,"
                "updated_at=? WHERE automation_id=?",
                (now, task["task_id"], task["status"], now, identifier),
            )
            self._database.execute(
                "UPDATE useful_automation_runs SET status=?,completed_at=?,task_id=? WHERE run_id=?",
                (task["status"], now, task["task_id"], run_id),
            )
            self._database.execute(
                "INSERT INTO useful_notifications VALUES(?,?,?,?,?,?,NULL)",
                (
                    str(uuid4()), "automation", record["name"],
                    f"Automation finished with status {task['status']}.",
                    task["task_id"], now,
                ),
            )
            return {
                "automation_id": identifier, "run_id": run_id,
                "status": task["status"], "task": task,
            }
        except Exception as error:
            self._database.execute(
                "UPDATE useful_automation_runs SET status='failed',completed_at=?,error=? "
                "WHERE run_id=?", (_now(), str(error)[:500], run_id),
            )
            raise
        finally:
            with self._lock:
                self._running.discard(identifier)

    def _update_state(self, identifier: str, state: dict) -> None:
        self._database.execute(
            "UPDATE useful_automations SET trigger_state_json=?,updated_at=? WHERE automation_id=?",
            (json.dumps(state, sort_keys=True), _now(), identifier),
        )

    def _run(self) -> None:
        while not self._stop.wait(self._poll_seconds):
            try:
                self.tick()
            except Exception:
                continue


def _automation(row) -> dict[str, object]:
    return {
        "automation_id": row[0], "name": row[1], "request": json.loads(row[2]),
        "trigger": json.loads(row[3]), "condition": json.loads(row[4]),
        "run_mode": row[5], "enabled": bool(row[6]), "created_at": row[7],
        "updated_at": row[8], "last_run_at": row[9], "last_task_id": row[10],
        "last_status": row[11],
    }


def _validate_trigger(trigger: dict) -> None:
    if trigger["type"] == "interval" and (
        not isinstance(trigger.get("seconds"), int) or trigger["seconds"] < 60
    ):
        raise ValueError("interval trigger must be at least 60 seconds")
    if trigger["type"] == "file_changed" and not isinstance(trigger.get("path"), str):
        raise ValueError("file_changed trigger requires a path")


def _initial_state(trigger: dict) -> dict:
    if trigger["type"] == "file_changed":
        path = Path(trigger["path"])
        return {"mtime_ns": path.stat().st_mtime_ns if path.exists() else None}
    return {}


def _condition_matches(condition: dict, path: Path) -> bool:
    suffix = condition.get("suffix")
    return suffix is None or (isinstance(suffix, str) and path.suffix.casefold() == suffix.casefold())


def _text(document: dict, name: str) -> str:
    value = document.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty text")
    return value.strip()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
