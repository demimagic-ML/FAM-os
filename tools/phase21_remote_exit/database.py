"""Content-free database observations for the installed remote-route gate."""

from __future__ import annotations

import sqlite3
from pathlib import Path


def database_observation(
    state_root: Path,
    plan_instance_ids: tuple[str, ...],
) -> dict:
    connection = sqlite3.connect(state_root / "state/fam.sqlite3")
    try:
        reservations = {
            plan_id: [
                {
                    "kind": row[0],
                    "reserved_tokens": row[1],
                    "reserved_wall_milliseconds": row[2],
                }
                for row in connection.execute(
                    """
                    SELECT kind, reserved_tokens, reserved_wall_milliseconds
                    FROM attempt_budget_reservations
                    WHERE plan_instance_id = ?
                    ORDER BY created_at, reservation_id
                    """,
                    (plan_id,),
                )
            ]
            for plan_id in plan_instance_ids
        }
        return {
            "request_count": _count(connection, "requests"),
            "inference_execution_count": _count(connection, "inference_executions"),
            "attempt_budget_count": _count(connection, "global_attempt_budgets"),
            "context_disclosure_count": _count(
                connection, "fabric_remote_context_disclosures",
            ),
            "final_evidence_counts": {
                plan_id: int(connection.execute(
                    "SELECT count(*) FROM final_evidence WHERE request_id = ?",
                    (_request_id(connection, plan_id),),
                ).fetchone()[0])
                for plan_id in plan_instance_ids
            },
            "reservations": reservations,
        }
    finally:
        connection.close()


def databases_contain(states: tuple[Path, ...], values: tuple[bytes, ...]) -> bool:
    return any(
        value in path.read_bytes()
        for state in states
        for path in (state / "state").glob("fam.sqlite3*")
        if path.is_file()
        for value in values
    )


def _count(connection: sqlite3.Connection, table: str) -> int:
    allowed = {
        "requests", "inference_executions", "global_attempt_budgets",
        "fabric_remote_context_disclosures",
    }
    if table not in allowed:
        raise ValueError("unsupported Phase 21.4 observation table")
    return int(connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0])


def _request_id(connection: sqlite3.Connection, plan_instance_id: str) -> str:
    row = connection.execute(
        "SELECT request_id FROM inference_executions WHERE instance_id = ?",
        (plan_instance_id,),
    ).fetchone()
    if row is None:
        raise RuntimeError(f"missing inference execution {plan_instance_id}")
    return str(row[0])
