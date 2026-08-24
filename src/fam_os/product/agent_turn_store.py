"""Durable SQLite storage for iterative agent threads and turn events."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from fam_os.core.agent import (
    AgentAuthorityProfile,
    AgentFinalResponse,
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
        })

    def complete_turn(
        self, thread_id: str, turn_id: str, response: AgentFinalResponse,
    ) -> None:
        cursor = self._database.execute(
            "UPDATE agent_turns SET status='completed',final_response=?,completed_at=? "
            "WHERE thread_id=? AND turn_id=? AND status='running'",
            (response.content, _now(), thread_id, turn_id),
        )
        if cursor.rowcount != 1:
            raise RuntimeError("agent turn completion state changed")

    def fail_turn(self, thread_id: str, turn_id: str, failure: str) -> None:
        cursor = self._database.execute(
            "UPDATE agent_turns SET status='failed',failure=?,completed_at=? "
            "WHERE thread_id=? AND turn_id=? AND status='running'",
            (failure, _now(), thread_id, turn_id),
        )
        if cursor.rowcount != 1:
            raise RuntimeError("agent turn failure state changed")

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
            "turns": [{
                "turn_id": item[0], "objective": item[1],
                "authority_profile": item[2], "status": item[3],
                "final_response": item[4], "failure": item[5],
                "created_at": item[6], "completed_at": item[7],
                "events": self.events(item[0]),
            } for item in turns],
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
