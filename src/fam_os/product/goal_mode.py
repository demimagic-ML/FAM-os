"""Durable background supervision for long-running natural engineering goals."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fam_os.core.agent import AgentAuthorityProfile
from fam_os.core.ports.inference import (
    InferenceMessage, InferenceRequest, MessageRole,
)


_TERMINAL = {"completed", "cancelled", "failed"}
_CONTROLLABLE = {"queued", "running", "pause_requested", "paused"}


class GoalModeService:
    """Persist, supervise, and recover owner-activated engineering goals."""

    def __init__(
        self, path: Path, natural_engineering, runtime, model_ref: str, *,
        poll_seconds: float = 0.5,
    ) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._database = sqlite3.connect(path, check_same_thread=False)
        self._database.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._api = natural_engineering
        self._runtime = runtime
        self._model_ref = model_ref
        self._poll_seconds = poll_seconds
        self._prepare()

    @property
    def owner_id(self) -> str:
        return self._api.owner_id

    def start(self) -> None:
        with self._lock, self._database:
            self._database.execute(
                "UPDATE engineering_goals SET status='queued',"
                "error='Recovered after FAM restarted.',updated_at=? "
                "WHERE status='running'",
                (_now(),),
            )
        if self._thread is None:
            self._thread = threading.Thread(
                target=self._run, daemon=True, name="fam-goal-supervisor",
            )
            self._thread.start()
        self._wake.set()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        with self._lock, self._database:
            rows = self._database.execute(
                "SELECT goal_id,owner_id,session_id,workspace_root FROM "
                "engineering_goals WHERE status='running'",
            ).fetchall()
            self._database.execute(
                "UPDATE engineering_goals SET status='restart_requested',control='restart',"
                "updated_at=? WHERE status='running'", (_now(),),
            )
        for row in rows:
            try:
                self._api.control_thread(
                    row["owner_id"], row["session_id"], row["workspace_root"],
                    "cancel", "FAM is stopping; checkpoint and pause this goal.",
                )
            except (KeyError, RuntimeError, ValueError):
                pass
        if self._thread is not None:
            self._thread.join(timeout=5)
            if self._thread.is_alive():
                return
            self._thread = None
        with self._lock:
            self._database.close()

    def prepare(
        self, owner_id: str, prompt: str, workspace_root: str,
        authority_profile: AgentAuthorityProfile, session_id: str,
    ) -> dict[str, object]:
        self._require_owner(owner_id)
        prompt = _text(prompt, "goal")
        workspace = Path(workspace_root).resolve(strict=True)
        if not workspace.is_dir():
            raise ValueError("goal workspace must be a directory")
        proposal = self._api.propose(
            owner_id, prompt, str(workspace), transport_session_id=session_id,
            authority_profile=authority_profile,
        )
        plan = self._plan(prompt, str(workspace))
        identifier, now = f"goal-{uuid4()}", _now()
        with self._lock, self._database:
            self._database.execute(
                "INSERT INTO engineering_goals("
                "goal_id,owner_id,session_id,workspace_root,prompt,title,plan_json,"
                "criteria_json,proposal_id,authority_profile,status,control,"
                "result_json,error,epochs,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,'',NULL,NULL,0,?,?)",
                (
                    identifier, owner_id, session_id, str(workspace), prompt,
                    plan["title"], json.dumps(plan["steps"], sort_keys=True),
                    json.dumps(plan["acceptance_criteria"], sort_keys=True),
                    proposal["proposal_id"], authority_profile.value, "draft",
                    now, now,
                ),
            )
        return self.inspect(owner_id, identifier)

    def activate(self, owner_id: str, goal_id: str, *, confirmed: bool) -> dict[str, object]:
        self._require_owner(owner_id)
        if confirmed is not True:
            raise PermissionError("goal activation requires confirmation")
        with self._lock, self._database:
            changed = self._database.execute(
                "UPDATE engineering_goals SET status='queued',control='',error=NULL,"
                "updated_at=? WHERE goal_id=? AND owner_id=? AND status IN ('draft','paused')",
                (_now(), goal_id, owner_id),
            ).rowcount
        if changed != 1:
            raise RuntimeError("goal cannot be activated from its current state")
        self._wake.set()
        return self.inspect(owner_id, goal_id)

    def control(
        self, owner_id: str, goal_id: str, action: str, content: str = "",
    ) -> dict[str, object]:
        self._require_owner(owner_id)
        if action not in {"pause", "resume", "cancel", "guide"}:
            raise ValueError("goal control action is unsupported")
        goal = self.inspect(owner_id, goal_id)
        status = str(goal["status"])
        if status in _TERMINAL:
            raise RuntimeError("completed goal cannot be controlled")
        if action == "guide":
            if status != "running":
                raise RuntimeError("guidance requires a running goal")
            instruction = _text(content, "guidance")
            self._api.control_thread(
                owner_id, str(goal["session_id"]), str(goal["workspace_root"]),
                "steer", instruction,
            )
            return self.inspect(owner_id, goal_id)
        if action == "resume":
            return self.activate(owner_id, goal_id, confirmed=True)
        target = "pause_requested" if action == "pause" else "cancel_requested"
        with self._lock, self._database:
            changed = self._database.execute(
                "UPDATE engineering_goals SET status=?,control=?,updated_at=? "
                "WHERE goal_id=? AND owner_id=? AND status IN ("
                "'queued','running','pause_requested','paused')",
                (target, action, _now(), goal_id, owner_id),
            ).rowcount
        if changed != 1:
            raise RuntimeError("goal control conflicts with its current state")
        if status == "running":
            self._api.control_thread(
                owner_id, str(goal["session_id"]), str(goal["workspace_root"]),
                "cancel", f"Goal {action} requested by owner.",
            )
        else:
            self._settle_control(goal_id)
        self._wake.set()
        return self.inspect(owner_id, goal_id)

    def inspect(self, owner_id: str, goal_id: str) -> dict[str, object]:
        self._require_owner(owner_id)
        with self._lock:
            row = self._database.execute(
                "SELECT * FROM engineering_goals WHERE goal_id=? AND owner_id=?",
                (goal_id, owner_id),
            ).fetchone()
        if row is None:
            raise KeyError("goal was not found")
        document = _document(row)
        document["live"] = self._live_progress(document)
        return document

    def list(self, owner_id: str, *, workspace_root: str | None = None) -> dict[str, object]:
        self._require_owner(owner_id)
        statement = "SELECT * FROM engineering_goals WHERE owner_id=?"
        parameters: tuple[object, ...] = (owner_id,)
        if workspace_root:
            statement += " AND workspace_root=?"
            parameters += (str(Path(workspace_root).resolve()),)
        statement += " ORDER BY created_at DESC LIMIT 50"
        with self._lock:
            rows = self._database.execute(statement, parameters).fetchall()
        return {"goals": [_document(row) for row in rows]}

    def _run(self) -> None:
        while not self._stop.is_set():
            goal = self._claim()
            if goal is None:
                self._wake.wait(self._poll_seconds)
                self._wake.clear()
                continue
            self._execute(goal)

    def _claim(self):
        with self._lock, self._database:
            row = self._database.execute(
                "SELECT goal_id FROM engineering_goals WHERE status='queued' "
                "ORDER BY created_at LIMIT 1",
            ).fetchone()
            if row is None:
                return None
            changed = self._database.execute(
                "UPDATE engineering_goals SET status='running',epochs=epochs+1,"
                "updated_at=? WHERE goal_id=? AND status='queued'",
                (_now(), row[0]),
            ).rowcount
            if changed != 1:
                return None
            return self._database.execute(
                "SELECT * FROM engineering_goals WHERE goal_id=?", (row[0],),
            ).fetchone()

    def _execute(self, row) -> None:
        goal_id = row["goal_id"]
        try:
            result = self._api.activate(
                row["owner_id"], row["proposal_id"], row["session_id"],
                confirmed=True, goal_mode=True,
            )
        except BaseException as error:
            with self._lock:
                current = self._database.execute(
                    "SELECT status FROM engineering_goals WHERE goal_id=?", (goal_id,),
                ).fetchone()
            if current and current[0] in {
                "pause_requested", "cancel_requested", "restart_requested",
            }:
                self._settle_control(goal_id)
                return
            with self._lock, self._database:
                self._database.execute(
                    "UPDATE engineering_goals SET status='failed',error=?,updated_at=? "
                    "WHERE goal_id=?",
                    (f"{type(error).__name__}: {str(error)[:2000]}", _now(), goal_id),
                )
            return
        task = result.get("engineering_task", {})
        pending_changeset = task.get("pending_changeset_id")
        if pending_changeset:
            try:
                result = self._api.approve_changeset(
                    row["owner_id"], row["proposal_id"], pending_changeset,
                    row["session_id"], confirmed=True,
                )
                task = result.get("engineering_task", {})
            except BaseException as error:
                with self._lock, self._database:
                    self._database.execute(
                        "UPDATE engineering_goals SET status='failed',error=?,"
                        "result_json=?,updated_at=? WHERE goal_id=?",
                        (
                            f"Final verified changes could not be applied: "
                            f"{type(error).__name__}: {str(error)[:1800]}",
                            json.dumps(result, sort_keys=True), _now(), goal_id,
                        ),
                    )
                return
        outcome = str(task.get("outcome", ""))
        status = (
            "waiting_approval"
            if outcome == "independent_review_blocked" else
            "completed" if not outcome.endswith("_failed") else "failed"
        )
        with self._lock, self._database:
            current = self._database.execute(
                "SELECT status FROM engineering_goals WHERE goal_id=?", (goal_id,),
            ).fetchone()
            if current and current[0] in {
                "pause_requested", "cancel_requested", "restart_requested",
            }:
                self._settle_control(goal_id)
                return
            self._database.execute(
                "UPDATE engineering_goals SET status=?,result_json=?,error=?,updated_at=? "
                "WHERE goal_id=?",
                (
                    status, json.dumps(result, sort_keys=True),
                    task.get("failure_code") if status == "failed" else None,
                    _now(), goal_id,
                ),
            )

    def _settle_control(self, goal_id: str) -> None:
        with self._lock, self._database:
            row = self._database.execute(
                "SELECT status FROM engineering_goals WHERE goal_id=?", (goal_id,),
            ).fetchone()
            if row is None:
                return
            target = (
                "cancelled" if row[0] == "cancel_requested" else
                "queued" if row[0] == "restart_requested" else "paused"
            )
            self._database.execute(
                "UPDATE engineering_goals SET status=?,updated_at=? WHERE goal_id=?",
                (target, _now(), goal_id),
            )

    def _plan(self, prompt: str, workspace: str) -> dict[str, object]:
        request = InferenceRequest(
            model_ref=self._model_ref,
            messages=(
                InferenceMessage(
                    MessageRole.SYSTEM,
                    "Create an executable engineering goal plan. Return strict JSON with "
                    "exactly title, steps, and acceptance_criteria. steps is an array of "
                    "3-8 concrete strings. acceptance_criteria is an array of 2-8 observable, "
                    "testable strings. Preserve the user's full objective; do not implement it.",
                ),
                InferenceMessage(MessageRole.USER, json.dumps({
                    "objective": prompt, "workspace": workspace,
                }, sort_keys=True)),
            ),
            context_tokens=16_384, max_output_tokens=2_048,
            keep_alive="30m", json_output=True, temperature=0.0, seed=44,
        )
        response = self._runtime.chat(request)
        try:
            value = json.loads(response.content)
        except (json.JSONDecodeError, TypeError) as error:
            raise RuntimeError("goal planner returned invalid JSON") from error
        if (
            not isinstance(value, dict) or set(value) != {
                "title", "steps", "acceptance_criteria",
            } or not isinstance(value["title"], str)
            or not _string_list(value["steps"], 3, 8)
            or not _string_list(value["acceptance_criteria"], 2, 8)
        ):
            raise RuntimeError("goal planner returned an invalid plan")
        return value

    def _prepare(self) -> None:
        with self._database:
            self._database.execute("PRAGMA journal_mode=WAL")
            self._database.execute(
                "CREATE TABLE IF NOT EXISTS engineering_goals("
                "goal_id TEXT PRIMARY KEY,owner_id TEXT NOT NULL,session_id TEXT NOT NULL,"
                "workspace_root TEXT NOT NULL,prompt TEXT NOT NULL,title TEXT NOT NULL,"
                "plan_json TEXT NOT NULL,criteria_json TEXT NOT NULL,proposal_id TEXT NOT NULL,"
                "authority_profile TEXT NOT NULL,status TEXT NOT NULL,control TEXT NOT NULL,"
                "result_json TEXT,error TEXT,epochs INTEGER NOT NULL,"
                "created_at TEXT NOT NULL,updated_at TEXT NOT NULL)"
            )

    def _require_owner(self, owner_id: str) -> None:
        if owner_id != self.owner_id:
            raise PermissionError("goal owner is invalid")

    def _live_progress(self, goal: dict[str, object]) -> dict[str, object] | None:
        if goal["status"] == "draft":
            return None
        try:
            thread = self._api.thread(
                self.owner_id,
                str(goal["session_id"]), str(goal["workspace_root"]),
            )
        except (
            AttributeError, KeyError, LookupError, PermissionError,
            RuntimeError, ValueError,
        ):
            return None
        if not isinstance(thread, dict):
            return None
        turns = thread.get("turns", [])
        if not turns:
            return None
        active = next(
            (turn for turn in reversed(turns) if turn.get("status") == "running"),
            turns[-1],
        )
        checkpoint = thread.get("latest_checkpoint") or {}
        raw_events = active.get("events", [])[-16:]
        events = [_compact_event(event) for event in raw_events]
        changed_files = sorted({
            path for event in raw_events
            for path in _event_paths(event)
        })[:24]
        state = checkpoint.get("state") or {}
        last_activity = (
            raw_events[-1].get("created_at") if raw_events
            else goal.get("updated_at")
        )
        return {
            "turn_id": active.get("turn_id"),
            "turn_status": active.get("status"),
            "node": checkpoint.get("node"),
            "phase": checkpoint.get("phase"),
            "step": checkpoint.get("step", 0),
            "sequence": checkpoint.get("sequence", 0),
            "model_ref": state.get("model_ref"),
            "escalated": bool(state.get("escalated")),
            "context_generation": state.get("context_generation", 0),
            "result_count": state.get("result_count", 0),
            "tool_count": state.get("tool_count", 0),
            "last_activity": last_activity,
            "changed_files": changed_files,
            "events": events,
        }


def _document(row: sqlite3.Row) -> dict[str, object]:
    result = None if row["result_json"] is None else json.loads(row["result_json"])
    task = {} if result is None else result.get("engineering_task", {})
    return {
        "goal_id": row["goal_id"], "session_id": row["session_id"],
        "workspace_root": row["workspace_root"], "prompt": row["prompt"],
        "title": row["title"], "plan": json.loads(row["plan_json"]),
        "acceptance_criteria": json.loads(row["criteria_json"]),
        "proposal_id": row["proposal_id"],
        "authority_profile": row["authority_profile"], "status": row["status"],
        "epochs": row["epochs"], "error": row["error"],
        "created_at": row["created_at"], "updated_at": row["updated_at"],
        "engineering_task": task,
    }


def _compact_event(event: dict[str, object]) -> dict[str, object]:
    payload = dict(event.get("payload") or {})
    output = payload.get("output")
    if isinstance(output, str) and len(output) > 1_200:
        payload["output"] = output[:1_200].rstrip() + "\n… output compacted"
    return {
        "call_id": event.get("call_id"), "tool_id": event.get("tool_id"),
        "event_kind": event.get("event_kind"), "payload": payload,
        "created_at": event.get("created_at"),
    }


def _event_paths(event: dict[str, object]) -> set[str]:
    payload = event.get("payload") or {}
    if not isinstance(payload, dict):
        return set()
    postcondition = payload.get("postcondition")
    if not isinstance(postcondition, dict):
        return set()
    paths: set[str] = set()
    pending = [postcondition]
    while pending:
        value = pending.pop()
        if isinstance(value, dict):
            for key, item in value.items():
                if key in {"path", "relative_path"} and isinstance(item, str):
                    paths.add(item)
                elif isinstance(item, (dict, list)):
                    pending.append(item)
        elif isinstance(value, list):
            pending.extend(item for item in value if isinstance(item, (dict, list)))
    return paths


def _string_list(value, minimum: int, maximum: int) -> bool:
    return (
        isinstance(value, list) and minimum <= len(value) <= maximum
        and all(isinstance(item, str) and item.strip() for item in value)
    )


def _text(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must not be empty")
    return value.strip()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
