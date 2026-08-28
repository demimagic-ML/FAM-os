"""Durable background supervision for long-running natural engineering goals."""

from __future__ import annotations

import json
import hashlib
import queue
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from fam_os.core.agent import AgentAuthorityProfile
from fam_os.core.ports.inference import (
    InferenceMessage, InferenceRequest, MessageRole,
    TransientInferenceError,
)


_TERMINAL = {"completed", "cancelled", "failed"}
_CONTROLLABLE = {
    "queued", "running", "retry_wait", "pause_requested", "paused",
}


class GoalModeService:
    """Persist, supervise, and recover owner-activated engineering goals."""

    def __init__(
        self, path: Path, natural_engineering, runtime, model_ref: str, *,
        poll_seconds: float = 0.5, maximum_recovery_attempts: int = 10,
        maximum_recovery_seconds: float = 1_800,
        retry_base_seconds: float = 2.0, retry_max_seconds: float = 60.0,
        watchdog_seconds: float = 240.0, provider_recover=None,
        system_snapshots=None, goal_notifier=None, sleeper=time.sleep,
    ) -> None:
        if maximum_recovery_attempts < 1 or maximum_recovery_seconds <= 0:
            raise ValueError("goal recovery budget must be positive")
        if retry_base_seconds <= 0 or retry_max_seconds < retry_base_seconds:
            raise ValueError("goal retry timing is invalid")
        if watchdog_seconds <= 0:
            raise ValueError("goal watchdog timing must be positive")
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
        self._maximum_recovery_attempts = maximum_recovery_attempts
        self._maximum_recovery_seconds = maximum_recovery_seconds
        self._retry_base_seconds = retry_base_seconds
        self._retry_max_seconds = retry_max_seconds
        self._watchdog_seconds = watchdog_seconds
        self._provider_recover = provider_recover
        self._system_snapshots = system_snapshots
        self._goal_notifier = goal_notifier
        self._sleep = sleeper
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
            resumable = self._database.execute(
                "SELECT owner_id,proposal_id,session_id FROM engineering_goals "
                "WHERE status IN ('queued','retry_wait','restart_requested')",
            ).fetchall()
        restore_grant = getattr(self._api, "restore_goal_grant", None)
        if callable(restore_grant):
            for row in resumable:
                restore_grant(row["owner_id"], row["proposal_id"], row["session_id"])
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
        transport_context: dict[str, object] | None = None,
    ) -> dict[str, object]:
        self._require_owner(owner_id)
        prompt = _text(prompt, "goal")
        workspace = Path(workspace_root).resolve(strict=True)
        if not workspace.is_dir():
            raise ValueError("goal workspace must be a directory")
        proposal_arguments = {
            "transport_session_id": session_id,
            "authority_profile": authority_profile,
        }
        if transport_context is not None:
            proposal_arguments["transport_context"] = transport_context
        proposal = self._api.propose(
            owner_id, prompt, str(workspace), **proposal_arguments,
        )
        plan = self._plan(prompt, str(workspace))
        identifier, now = f"goal-{uuid4()}", _now()
        with self._lock, self._database:
            self._database.execute(
                "INSERT INTO engineering_goals("
                "goal_id,owner_id,session_id,workspace_root,prompt,title,plan_json,"
                "criteria_json,proposal_id,authority_profile,status,control,"
                "result_json,error,epochs,created_at,updated_at,transport_context_json) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,'',NULL,NULL,0,?,?,?)",
                (
                    identifier, owner_id, session_id, str(workspace), prompt,
                    plan["title"], json.dumps(plan["steps"], sort_keys=True),
                    json.dumps(plan["acceptance_criteria"], sort_keys=True),
                    proposal["proposal_id"], authority_profile.value, "draft",
                    now, now,
                    None if transport_context is None else json.dumps(
                        transport_context, separators=(",", ":"), sort_keys=True,
                    ),
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
                "'queued','running','retry_wait','pause_requested','paused')",
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
        document["candidate"] = self._candidate_progress(document)
        document["system_snapshot"] = (
            None if row["snapshot_json"] is None
            else json.loads(row["snapshot_json"])
        )
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
                "SELECT goal_id FROM engineering_goals WHERE status='queued' OR "
                "(status='retry_wait' AND next_retry_at<=?) "
                "ORDER BY created_at LIMIT 1",
                (_now(),),
            ).fetchone()
            if row is None:
                return None
            changed = self._database.execute(
                "UPDATE engineering_goals SET status='running',epochs=epochs+1,"
                "next_retry_at=NULL,updated_at=? WHERE goal_id=? AND "
                "status IN ('queued','retry_wait')",
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
            if int(row["retry_attempts"]):
                self._recover_provider()
            self._ensure_system_snapshot(row)
            if row["execution_stage"] == "apply":
                result = json.loads(row["result_json"] or "{}")
            else:
                result = self._watched_call(
                    row,
                    lambda: self._api.activate(
                        row["owner_id"], row["proposal_id"], row["session_id"],
                        confirmed=True, goal_mode=True,
                    ),
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
            self._record_failure(row, error)
            return
        task = result.get("engineering_task", {})
        changeset = task.get("changeset") or {}
        changeset_payload = (
            changeset.get("payload", {}) if isinstance(changeset, dict) else {}
        )
        pending_changeset = (
            task.get("pending_changeset_id")
            or changeset_payload.get("changeset_id")
        )
        if pending_changeset:
            with self._lock, self._database:
                self._database.execute(
                    "UPDATE engineering_goals SET execution_stage='apply',"
                    "pending_changeset_id=?,result_json=?,updated_at=? WHERE goal_id=?",
                    (
                        pending_changeset, json.dumps(result, sort_keys=True),
                        _now(), goal_id,
                    ),
                )
            try:
                result = self._api.approve_changeset(
                    row["owner_id"], row["proposal_id"], pending_changeset,
                    row["session_id"], confirmed=True,
                )
                task = result.get("engineering_task", {})
            except BaseException as error:
                self._record_failure(row, error, result=result, stage="apply")
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
                "UPDATE engineering_goals SET status=?,result_json=?,error=?,"
                "execution_stage='complete',next_retry_at=NULL,updated_at=? "
                "WHERE goal_id=?",
                (
                    status, json.dumps(result, sort_keys=True),
                    task.get("failure_code") if status == "failed" else None,
                    _now(), goal_id,
                ),
            )
        self._notify(
            goal_id, status, row["title"],
            str(task.get("failure_code") or ""),
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

    def _record_failure(self, row, error, *, result=None, stage=None) -> None:
        goal_id = row["goal_id"]
        failure = f"{type(error).__name__}: {str(error)[:2_000]}"
        if not _transient(error):
            with self._lock, self._database:
                self._database.execute(
                    "UPDATE engineering_goals SET status='failed',error=?,"
                    "result_json=COALESCE(?,result_json),updated_at=? WHERE goal_id=?",
                    (
                        failure,
                        None if result is None else json.dumps(result, sort_keys=True),
                        _now(), goal_id,
                    ),
                )
            self._notify(goal_id, "failed", row["title"], failure)
            return
        now = datetime.now(timezone.utc)
        with self._lock:
            current = self._database.execute(
                "SELECT retry_attempts,recovery_started_at,last_checkpoint_sequence,"
                "last_result_count,execution_stage "
                "FROM engineering_goals WHERE goal_id=?", (goal_id,),
            ).fetchone()
        sequence, result_count = self._checkpoint_progress(row)
        progressed = (
            result_count > int(current["last_result_count"] or 0)
            or (stage == "apply" and current["execution_stage"] != "apply")
        )
        started = (
            now if progressed or not current["recovery_started_at"]
            else datetime.fromisoformat(current["recovery_started_at"])
        )
        attempts = 1 if progressed else int(current["retry_attempts"]) + 1
        exhausted = (
            attempts > self._maximum_recovery_attempts
            or (now - started).total_seconds() >= self._maximum_recovery_seconds
        )
        if exhausted:
            with self._lock, self._database:
                self._database.execute(
                    "UPDATE engineering_goals SET status='failed',error=?,"
                    "retry_attempts=?,last_checkpoint_sequence=?,last_result_count=?,"
                    "updated_at=? "
                    "WHERE goal_id=?",
                    (
                        f"recovery_budget_exhausted: {failure}", attempts,
                        sequence, result_count, now.isoformat(), goal_id,
                    ),
                )
            self._notify(
                goal_id, "failed", row["title"],
                f"Recovery budget exhausted after {attempts} attempts.",
                recovery_attempt=attempts,
            )
            return
        delay = self._retry_delay(goal_id, attempts)
        next_retry = now + timedelta(seconds=delay)
        with self._lock, self._database:
            self._database.execute(
                "UPDATE engineering_goals SET status='retry_wait',error=?,"
                "retry_attempts=?,recovery_started_at=?,next_retry_at=?,"
                "last_checkpoint_sequence=?,last_result_count=?,"
                "execution_stage=COALESCE(?,execution_stage),"
                "result_json=COALESCE(?,result_json),updated_at=? WHERE goal_id=?",
                (
                    failure, attempts, started.isoformat(), next_retry.isoformat(),
                    sequence, result_count, stage,
                    None if result is None else json.dumps(result, sort_keys=True),
                    now.isoformat(), goal_id,
                ),
            )
        self._wake.set()
        self._notify(
            goal_id, "retry_wait", row["title"],
            f"Recovery attempt {attempts}; retrying after a transient failure.",
            recovery_attempt=attempts,
        )

    def _notify(
        self, goal_id: str, status: str, title: str, detail: str = "", *,
        recovery_attempt: int = 0,
    ) -> None:
        if not callable(self._goal_notifier):
            return
        try:
            self._goal_notifier(
                goal_id, status, title, detail,
                recovery_attempt=recovery_attempt,
            )
        except (OSError, RuntimeError, ValueError):
            pass

    def _checkpoint_sequence(self, row) -> int:
        return self._checkpoint_progress(row)[0]

    def _checkpoint_progress(self, row) -> tuple[int, int]:
        try:
            thread = self._api.thread(
                row["owner_id"], row["session_id"], row["workspace_root"],
            )
        except (AttributeError, KeyError, LookupError, PermissionError, RuntimeError):
            return 0, 0
        checkpoint = thread.get("latest_checkpoint") if isinstance(thread, dict) else None
        state = (checkpoint or {}).get("state") or {}
        return (
            int((checkpoint or {}).get("sequence") or 0),
            int(state.get("result_count") or 0),
        )

    def _retry_delay(self, goal_id: str, attempt: int) -> float:
        base = min(
            self._retry_max_seconds,
            self._retry_base_seconds * (2 ** max(0, attempt - 1)),
        )
        digest = hashlib.sha256(f"{goal_id}:{attempt}".encode()).digest()[0]
        jitter = .85 + (digest / 255) * .3
        return round(base * jitter, 3)

    def _recover_provider(self) -> None:
        loaded = getattr(self._runtime, "loaded_models", None)
        prewarm = getattr(self._runtime, "prewarm", None)
        if not callable(loaded):
            return
        try:
            models = loaded()
        except TransientInferenceError:
            if not callable(self._provider_recover):
                raise
            self._provider_recover()
            models = loaded()
        if (
            callable(prewarm)
            and not any(item.model_ref == self._model_ref for item in models)
        ):
            prewarm(self._model_ref, "30m")

    def _ensure_system_snapshot(self, row) -> None:
        if (
            row["snapshot_json"] is not None
            or not _requires_system_snapshot(row)
            or self._system_snapshots is None
            or not self._system_snapshots.available()
        ):
            return
        receipt = self._system_snapshots.create(
            f"FAM_OS preflight for {row['title']} ({row['goal_id']})",
        )
        document = {
            "available": receipt.available,
            "created": receipt.created,
            "reference": receipt.reference,
            "references": list(getattr(receipt, "references", ())),
            "recovery_command": getattr(receipt, "recovery_command", None),
            "detail": receipt.detail,
            "created_at": _now(),
        }
        if not receipt.created:
            raise RuntimeError(
                "Omarchy preflight snapshot failed: " + receipt.detail,
            )
        with self._lock, self._database:
            self._database.execute(
                "UPDATE engineering_goals SET snapshot_json=?,updated_at=? "
                "WHERE goal_id=? AND snapshot_json IS NULL",
                (json.dumps(document, sort_keys=True), _now(), row["goal_id"]),
            )

    def _watched_call(self, row, operation):
        outcomes: queue.Queue = queue.Queue(maxsize=1)

        def run_operation():
            try:
                outcomes.put((True, operation()))
            except BaseException as error:
                outcomes.put((False, error))

        worker = threading.Thread(
            target=run_operation, daemon=True,
            name=f"fam-goal-operation-{row['goal_id'][-8:]}",
        )
        worker.start()
        sequence = self._checkpoint_sequence(row)
        progress_at = time.monotonic()
        watchdog_tripped = False
        while True:
            try:
                succeeded, value = outcomes.get(timeout=self._poll_seconds)
                if succeeded:
                    return value
                raise value
            except queue.Empty:
                current = self._checkpoint_sequence(row)
                if current > sequence:
                    sequence, progress_at = current, time.monotonic()
                    watchdog_tripped = False
                if (
                    not watchdog_tripped
                    and time.monotonic() - progress_at >= self._watchdog_seconds
                ):
                    watchdog_tripped = True
                    with self._lock, self._database:
                        self._database.execute(
                            "UPDATE engineering_goals SET watchdog_trips="
                            "watchdog_trips+1,error=?,updated_at=? WHERE goal_id=?",
                            (
                                "watchdog detected a stalled model request; "
                                "recovering the inference provider",
                                _now(), row["goal_id"],
                            ),
                        )
                    if callable(self._provider_recover):
                        try:
                            self._provider_recover()
                        except (OSError, RuntimeError, ValueError):
                            pass

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
        response = None
        recovery_started = time.monotonic()
        for attempt in range(1, self._maximum_recovery_attempts + 2):
            try:
                response = self._runtime.chat(request)
                break
            except BaseException as error:
                exhausted = (
                    attempt > self._maximum_recovery_attempts
                    or time.monotonic() - recovery_started
                    >= self._maximum_recovery_seconds
                )
                if not _transient(error) or exhausted:
                    raise
                try:
                    self._recover_provider()
                except (OSError, RuntimeError, ValueError):
                    pass
                self._sleep(min(
                    self._retry_max_seconds,
                    self._retry_base_seconds * (2 ** (attempt - 1)),
                ))
        if response is None:
            raise RuntimeError("goal planner did not produce a response")
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
            columns = {
                row[1] for row in self._database.execute(
                    "PRAGMA table_info(engineering_goals)"
                ).fetchall()
            }
            additions = {
                "retry_attempts": "INTEGER NOT NULL DEFAULT 0",
                "recovery_started_at": "TEXT",
                "next_retry_at": "TEXT",
                "last_checkpoint_sequence": "INTEGER NOT NULL DEFAULT 0",
                "last_result_count": "INTEGER NOT NULL DEFAULT 0",
                "execution_stage": "TEXT NOT NULL DEFAULT 'activation'",
                "pending_changeset_id": "TEXT",
            "watchdog_trips": "INTEGER NOT NULL DEFAULT 0",
            "snapshot_json": "TEXT",
            "transport_context_json": "TEXT",
            }
            for name, definition in additions.items():
                if name not in columns:
                    self._database.execute(
                        f"ALTER TABLE engineering_goals ADD COLUMN {name} {definition}"
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
        all_events = active.get("events", [])
        raw_events = all_events[-16:]
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
            "application_test": _application_test_progress(all_events),
            "events": events,
        }

    def _candidate_progress(
        self, goal: dict[str, object],
    ) -> dict[str, object] | None:
        reader = getattr(self._api, "candidate_workspace", None)
        if not callable(reader):
            return None
        try:
            candidate = reader(self.owner_id, str(goal["proposal_id"]))
        except (
            AttributeError, KeyError, LookupError, OSError,
            PermissionError, RuntimeError, ValueError,
        ):
            return None
        candidate["state"] = (
            "applied" if goal["status"] == "completed"
            else "ready" if goal["status"] == "waiting_approval"
            else "isolated"
        )
        return candidate


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
        "transport_context": (
            None if row["transport_context_json"] is None
            else json.loads(row["transport_context_json"])
        ),
        "recovery": {
            "attempt": row["retry_attempts"],
            "next_retry_at": row["next_retry_at"],
            "started_at": row["recovery_started_at"],
            "watchdog_trips": row["watchdog_trips"],
            "stage": row["execution_stage"],
        },
    }


def _requires_system_snapshot(row: sqlite3.Row) -> bool:
    if row["authority_profile"] != AgentAuthorityProfile.FULL_OS.value:
        return False
    text = " ".join((
        str(row["prompt"]), str(row["title"]), str(row["plan_json"]),
    )).casefold()
    return any(marker in text for marker in (
        "pacman", "system package", "install package", "remove package",
        "machine configuration", "system configuration", "systemd",
        "/etc/", "hyprland config", "quickshell config", "kernel",
    ))


def _application_test_progress(
    events: list[dict[str, object]],
) -> dict[str, object] | None:
    calls = [
        event for event in events
        if event.get("event_kind") == "call"
        and str(event.get("tool_id", "")).startswith(("app_", "native_app_"))
    ]
    if not calls:
        return None
    results = {
        event.get("call_id"): event for event in events
        if event.get("event_kind") == "result"
    }

    def output(call):
        result = results.get(call.get("call_id"), {})
        payload = result.get("payload") or {}
        value = payload.get("output") if isinstance(payload, dict) else None
        if not isinstance(value, str):
            return {}
        try:
            document = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return document if isinstance(document, dict) else {}

    native = any(str(item.get("tool_id", "")).startswith("native_app_") for item in calls)
    prefix = "native_app_" if native else "app_"
    start = next((item for item in reversed(calls) if item.get("tool_id") == prefix + "start"), None)
    stop = next((item for item in reversed(calls) if item.get("tool_id") == prefix + "stop"), None)
    started = output(start) if start is not None else {}
    stopped = output(stop) if stop is not None else {}
    assertions = sum(
        output(item).get("passed") is True
        for item in calls if item.get("tool_id") == prefix + "assert"
    )
    console = next((
        output(item) for item in reversed(calls)
        if item.get("tool_id") == "app_console_errors"
    ), {})
    network = next((
        output(item) for item in reversed(calls)
        if item.get("tool_id") == "app_network_failures"
    ), {})
    return {
        "session_id": started.get("session_id"),
        "resumed_from": started.get("resumed_from"),
        "status": "completed" if stop is not None else "running",
        "assertions_passed": assertions,
        "planned_checks": len((started.get("plan") or {}).get("checks", [])),
        "console_errors": console.get("count", len(stopped.get("console_events", []))),
        "network_failures": network.get("count", len(stopped.get("network_events", []))),
        "provider": "at-spi" if native else "playwright",
        "latest_action": str(calls[-1].get("tool_id", prefix + "start")),
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
    paths: set[str] = set()
    output = payload.get("output")
    if isinstance(output, str):
        for line in output.splitlines():
            operation, separator, path = line.partition("\t")
            if (
                separator and operation in {
                    "create_file", "patch_file", "delete_file",
                    "create_directory", "delete_directory",
                } and path.strip()
            ):
                paths.add(path.strip().removeprefix("./"))
    postcondition = payload.get("postcondition")
    if not isinstance(postcondition, dict):
        return paths
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


def _transient(error: BaseException) -> bool:
    current: BaseException | None = error
    inspected = 0
    while current is not None and inspected < 8:
        if isinstance(current, (TransientInferenceError, TimeoutError, ConnectionError)):
            return True
        current = current.__cause__ or current.__context__
        inspected += 1
    return False


def _text(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must not be empty")
    return value.strip()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
