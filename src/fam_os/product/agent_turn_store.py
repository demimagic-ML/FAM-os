"""Durable SQLite storage for iterative agent threads and turn events."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from fam_os.core.agent import (
    AgentAuthorityProfile,
    AgentExecutionCheckpoint,
    AgentFinalResponse,
    AgentGoalLedger,
    AgentGraphNode,
    AgentToolCall,
    AgentToolResult,
)


class SQLiteAgentTurnStore:
    def __init__(self, database, workspace_root: str) -> None:
        if not workspace_root.strip():
            raise ValueError("agent workspace root must not be empty")
        self._database = database
        self._workspace_root = workspace_root

    def begin_turn(
        self, thread_id: str, turn_id: str, objective: str,
        profile: AgentAuthorityProfile,
    ) -> None:
        now = _now()
        with self._database.transaction() as connection:
            existing_turn = connection.execute(
                "SELECT objective,authority_profile,status FROM agent_turns "
                "WHERE thread_id=? AND turn_id=?", (thread_id, turn_id),
            ).fetchone()
            if existing_turn is not None:
                if (
                    existing_turn[0] != objective
                    or existing_turn[1] != profile.value
                    or existing_turn[2] != "running"
                ):
                    raise RuntimeError("agent turn identity cannot be reused")
                return
            row = connection.execute(
                "SELECT workspace_root,authority_profile FROM agent_threads "
                "WHERE thread_id=?", (thread_id,),
            ).fetchone()
            if row is None:
                connection.execute(
                    "INSERT INTO agent_threads(thread_id,workspace_root,authority_profile,"
                    "created_at,updated_at) VALUES(?,?,?,?,?)",
                    (thread_id, self._workspace_root, profile.value, now, now),
                )
            elif row[0] != self._workspace_root:
                raise PermissionError("agent thread workspace cannot change")
            else:
                connection.execute(
                    "UPDATE agent_threads SET authority_profile=?,updated_at=? "
                    "WHERE thread_id=?",
                    (profile.value, now, thread_id),
                )
            connection.execute(
                "INSERT INTO agent_turns(turn_id,thread_id,objective,authority_profile,"
                "status,created_at) VALUES(?,?,?,?,?,?)",
                (turn_id, thread_id, objective, profile.value, "running", now),
            )
            ledger = connection.execute(
                "SELECT 1 FROM agent_goal_ledgers WHERE thread_id=?", (thread_id,),
            ).fetchone()
            if ledger is None:
                connection.execute(
                    "INSERT INTO agent_goal_ledgers(thread_id,original_request,"
                    "current_objective,unresolved_items_json,created_at,updated_at) "
                    "VALUES(?,?,?,?,?,?)",
                    (thread_id, objective, objective, json.dumps([objective]), now, now),
                )
            else:
                connection.execute(
                    "UPDATE agent_goal_ledgers SET current_objective=?,"
                    "unresolved_items_json=?,updated_at=? WHERE thread_id=?",
                    (objective, json.dumps([objective]), now, thread_id),
                )

    def restore_turn(
        self, thread_id: str, turn_id: str,
    ) -> tuple[tuple[AgentToolCall, AgentToolResult], ...]:
        rows = self._database.fetchall(
            "SELECT call_id,tool_id,event_kind,payload_json FROM agent_tool_events "
            "WHERE thread_id=? AND turn_id=? ORDER BY event_id",
            (thread_id, turn_id),
        )
        calls: dict[str, AgentToolCall] = {}
        restored: list[tuple[AgentToolCall, AgentToolResult]] = []
        for call_id, tool_id, kind, payload_json in rows:
            payload = json.loads(payload_json)
            if kind == "call":
                calls[call_id] = AgentToolCall(
                    call_id, tool_id, payload["arguments"], payload["reason"],
                )
            elif kind == "result" and call_id in calls:
                restored.append((calls.pop(call_id), AgentToolResult(
                    call_id, tool_id, bool(payload["succeeded"]),
                    payload["output"], payload.get("postcondition"),
                )))
        for call in calls.values():
            restored.append((call, AgentToolResult(
                call.call_id, call.tool_id, False,
                "Execution outcome is unknown after interruption. Observe the "
                "requested postcondition before deciding whether to retry; do not "
                "blindly replay this mutation.",
            )))
        return tuple(restored)

    def goal_ledger(self, thread_id: str) -> AgentGoalLedger:
        row = self._database.fetchone(
            "SELECT original_request,accepted_plan,current_objective,"
            "completed_objectives_json,unresolved_items_json "
            "FROM agent_goal_ledgers WHERE thread_id=?", (thread_id,),
        )
        if row is None:
            raise LookupError("agent goal ledger is unavailable")
        return AgentGoalLedger(
            row[0], row[1], row[2], tuple(json.loads(row[3])), tuple(json.loads(row[4])),
        )

    def context_state(self, thread_id: str) -> tuple[int, int]:
        row = self._database.fetchone(
            "SELECT context_generation,compaction_count FROM agent_goal_ledgers "
            "WHERE thread_id=?", (thread_id,),
        )
        return (0, 0) if row is None else (int(row[0]), int(row[1]))

    def completed_turn(self, thread_id: str, turn_id: str) -> str | None:
        row = self._database.fetchone(
            "SELECT final_response FROM agent_turns WHERE thread_id=? AND turn_id=? "
            "AND status='completed'",
            (thread_id, turn_id),
        )
        return None if row is None else str(row[0])

    def record_compaction(self, thread_id: str, generation: int) -> None:
        self._database.execute(
            "UPDATE agent_goal_ledgers SET context_generation=?,compaction_count="
            "compaction_count+1,updated_at=? WHERE thread_id=?",
            (generation, _now(), thread_id),
        )

    def checkpoint(
        self, checkpoint: AgentExecutionCheckpoint,
    ) -> None:
        self._database.execute(
            "INSERT INTO agent_execution_checkpoints(thread_id,turn_id,sequence,"
            "graph_node,model_step,phase,state_json,created_at) VALUES(?,?,?,?,?,?,?,?)",
            (
                checkpoint.thread_id, checkpoint.turn_id, checkpoint.sequence,
                checkpoint.node.value, checkpoint.step, checkpoint.phase,
                json.dumps(checkpoint.state, sort_keys=True, separators=(",", ":")),
                _now(),
            ),
        )

    def latest_checkpoint(
        self, thread_id: str, turn_id: str | None = None,
    ) -> AgentExecutionCheckpoint | None:
        clause = "thread_id=?" if turn_id is None else "thread_id=? AND turn_id=?"
        parameters = (thread_id,) if turn_id is None else (thread_id, turn_id)
        row = self._database.fetchone(
            "SELECT turn_id,sequence,graph_node,model_step,phase,state_json "
            f"FROM agent_execution_checkpoints WHERE {clause} "
            "ORDER BY checkpoint_id DESC LIMIT 1", parameters,
        )
        if row is None:
            return None
        return AgentExecutionCheckpoint(
            thread_id, row[0], int(row[1]), AgentGraphNode(row[2]), int(row[3]),
            row[4], json.loads(row[5]),
        )

    def conversation_context(self, thread_id: str) -> str:
        rows = self._database.fetchall(
            "SELECT objective,final_response FROM agent_turns "
            "WHERE thread_id=? AND status='completed' "
            "ORDER BY created_at DESC,turn_id DESC LIMIT 12",
            (thread_id,),
        )
        if not rows:
            return ""
        turns = [
            f"User: {objective}\nFAM: {response}"
            for objective, response in reversed(rows)
            if response
        ]
        return _bounded("\n\n".join(turns), 24_000)

    def record_call(
        self, thread_id: str, turn_id: str, call: AgentToolCall,
    ) -> None:
        self._event(thread_id, turn_id, call.call_id, call.tool_id, "call", {
            "arguments": call.arguments,
            "reason": call.reason,
        })

    def record_result(
        self, thread_id: str, turn_id: str, result: AgentToolResult,
    ) -> None:
        self._event(thread_id, turn_id, result.call_id, result.tool_id, "result", {
            "succeeded": result.succeeded,
            "output": result.output,
            "postcondition": result.postcondition,
        })

    def complete_turn(
        self, thread_id: str, turn_id: str, response: AgentFinalResponse,
    ) -> None:
        now = _now()
        with self._database.transaction() as connection:
            row = connection.execute(
                "SELECT objective FROM agent_turns WHERE thread_id=? AND turn_id=? "
                "AND status='running'", (thread_id, turn_id),
            ).fetchone()
            if row is None:
                raise RuntimeError("agent turn completion state changed")
            connection.execute(
                "UPDATE agent_turns SET status='completed',final_response=?,completed_at=? "
                "WHERE thread_id=? AND turn_id=?",
                (response.content, now, thread_id, turn_id),
            )
            ledger = connection.execute(
                "SELECT completed_objectives_json FROM agent_goal_ledgers "
                "WHERE thread_id=?", (thread_id,),
            ).fetchone()
            completed = [] if ledger is None else json.loads(ledger[0])
            if row[0] not in completed:
                completed.append(row[0])
            connection.execute(
                "UPDATE agent_goal_ledgers SET accepted_plan=?,"
                "completed_objectives_json=?,unresolved_items_json='[]',updated_at=? "
                "WHERE thread_id=?",
                (response.content, json.dumps(completed[-32:]), now, thread_id),
            )

    def fail_turn(self, thread_id: str, turn_id: str, failure: str) -> None:
        cursor = self._database.execute(
            "UPDATE agent_turns SET status='failed',failure=?,completed_at=? "
            "WHERE thread_id=? AND turn_id=? AND status='running'",
            (failure, _now(), thread_id, turn_id),
        )
        if cursor.rowcount != 1:
            raise RuntimeError("agent turn failure state changed")

    def cancel_turn(self, thread_id: str, turn_id: str, reason: str) -> None:
        cursor = self._database.execute(
            "UPDATE agent_turns SET status='cancelled',failure=?,completed_at=? "
            "WHERE thread_id=? AND turn_id=? AND status='running'",
            (reason, _now(), thread_id, turn_id),
        )
        if cursor.rowcount != 1:
            raise RuntimeError("agent turn cancellation state changed")

    def request_control(
        self, thread_id: str, kind: str, content: str,
    ) -> None:
        if kind not in {"steer", "cancel"} or not content.strip():
            raise ValueError("agent control is invalid")
        row = self._database.fetchone(
            "SELECT 1 FROM agent_turns WHERE thread_id=? AND status='running'",
            (thread_id,),
        )
        if row is None:
            raise LookupError("agent thread has no running turn")
        self._database.execute(
            "INSERT INTO agent_thread_controls(thread_id,control_kind,content,created_at) "
            "VALUES(?,?,?,?)", (thread_id, kind, content, _now()),
        )

    def consume_controls(self, thread_id: str) -> tuple[dict[str, str], ...]:
        consumed = _now()
        with self._database.transaction() as connection:
            rows = connection.execute(
                "SELECT control_id,control_kind,content FROM agent_thread_controls "
                "WHERE thread_id=? AND consumed_at IS NULL ORDER BY control_id",
                (thread_id,),
            ).fetchall()
            if rows:
                connection.executemany(
                    "UPDATE agent_thread_controls SET consumed_at=? WHERE control_id=?",
                    ((consumed, row[0]) for row in rows),
                )
        return tuple({"kind": row[1], "content": row[2]} for row in rows)

    def thread(self, thread_id: str) -> dict[str, object] | None:
        row = self._database.fetchone(
            "SELECT workspace_root,authority_profile,created_at,updated_at "
            "FROM agent_threads WHERE thread_id=?", (thread_id,),
        )
        if row is None:
            return None
        turns = self._database.fetchall(
            "SELECT turn_id,objective,authority_profile,status,final_response,"
            "failure,created_at,completed_at FROM agent_turns WHERE thread_id=? "
            "ORDER BY created_at,turn_id", (thread_id,),
        )
        return {
            "thread_id": thread_id,
            "workspace_root": row[0],
            "authority_profile": row[1],
            "created_at": row[2],
            "updated_at": row[3],
            "goal_ledger": self._ledger_dict(thread_id),
            "latest_checkpoint": self._checkpoint_dict(
                self.latest_checkpoint(thread_id),
            ),
            "turns": [{
                "turn_id": item[0], "objective": item[1],
                "authority_profile": item[2], "status": item[3],
                "final_response": item[4], "failure": item[5],
                "created_at": item[6], "completed_at": item[7],
                "events": self.events(item[0]),
            } for item in turns],
        }

    def _ledger_dict(self, thread_id: str) -> dict[str, object] | None:
        try:
            ledger = self.goal_ledger(thread_id)
        except LookupError:
            return None
        return {
            "original_request": ledger.original_request,
            "accepted_plan": ledger.accepted_plan,
            "current_objective": ledger.current_objective,
            "completed_objectives": list(ledger.completed_objectives),
            "unresolved_items": list(ledger.unresolved_items),
        }

    @staticmethod
    def _checkpoint_dict(checkpoint) -> dict[str, object] | None:
        if checkpoint is None:
            return None
        return {
            "turn_id": checkpoint.turn_id,
            "sequence": checkpoint.sequence,
            "node": checkpoint.node.value,
            "step": checkpoint.step,
            "phase": checkpoint.phase,
            "state": checkpoint.state,
        }

    def events(self, turn_id: str) -> list[dict[str, object]]:
        rows = self._database.fetchall(
            "SELECT call_id,tool_id,event_kind,payload_json,created_at "
            "FROM agent_tool_events WHERE turn_id=? ORDER BY event_id", (turn_id,),
        )
        return [{
            "call_id": row[0], "tool_id": row[1], "event_kind": row[2],
            "payload": json.loads(row[3]), "created_at": row[4],
        } for row in rows]

    def _event(self, thread_id, turn_id, call_id, tool_id, kind, payload) -> None:
        self._database.execute(
            "INSERT INTO agent_tool_events(thread_id,turn_id,call_id,tool_id,"
            "event_kind,payload_json,created_at) VALUES(?,?,?,?,?,?,?)",
            (thread_id, turn_id, call_id, tool_id, kind,
             json.dumps(payload, sort_keys=True, separators=(",", ":")), _now()),
        )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _bounded(value: str, maximum_bytes: int) -> str:
    encoded = value.encode("utf-8")
    if len(encoded) <= maximum_bytes:
        return value
    return encoded[-maximum_bytes:].decode("utf-8", errors="ignore")
