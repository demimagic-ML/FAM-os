"""SQLite persistence for user-facing tasks and their produced artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from fam_os.product.useful_tasks.contracts import UsefulArtifact, UsefulTask


class UsefulTaskRepository:
    def __init__(self, database) -> None:
        self._database = database

    def create(
        self, task_id: str, workflow_id: str, prompt: str, workspace_root: Path,
        timestamp: str, request_document: dict[str, object],
        parent_task_id: str | None = None, project_id: str | None = None,
    ) -> None:
        self._database.execute(
            "INSERT INTO useful_tasks(task_id,workflow_id,prompt,workspace_root,status,"
            "created_at,updated_at,request_json,parent_task_id,project_id) "
            "VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                task_id, workflow_id, prompt, str(workspace_root), "running", timestamp,
                timestamp, json.dumps(request_document, sort_keys=True), parent_task_id, project_id,
            ),
        )

    def complete(
        self, task_id: str, summary: str, timestamp: str,
        continuation: dict[str, object] | None = None,
    ) -> None:
        self._database.execute(
            "UPDATE useful_tasks SET status='completed',summary=?,continuation_json=?,"
            "updated_at=? WHERE task_id=?",
            (
                summary,
                None if continuation is None else json.dumps(continuation, sort_keys=True),
                timestamp,
                task_id,
            ),
        )

    def fail(self, task_id: str, error: str, timestamp: str) -> None:
        self._database.execute(
            "UPDATE useful_tasks SET status='failed',error=?,updated_at=? WHERE task_id=?",
            (error, timestamp, task_id),
        )

    def add_artifact(self, artifact: UsefulArtifact) -> None:
        self._database.execute(
            "INSERT INTO useful_artifacts(artifact_id,task_id,kind,path,media_type,sha256,"
            "size_bytes) VALUES(?,?,?,?,?,?,?)",
            (
                artifact.artifact_id, artifact.task_id, artifact.kind, str(artifact.path),
                artifact.media_type, artifact.sha256, artifact.size_bytes,
            ),
        )

    def get(self, task_id: str) -> UsefulTask | None:
        row = self._database.fetchone(
            "SELECT task_id,workflow_id,prompt,workspace_root,status,created_at,updated_at,"
            "summary,error,continuation_json,parent_task_id,project_id "
            "FROM useful_tasks WHERE task_id=?",
            (task_id,),
        )
        return None if row is None else self._decode(row)

    def list(
        self, *, limit: int = 50, offset: int = 0, query: str | None = None,
        project_id: str | None = None, attention_only: bool = False,
    ) -> tuple[UsefulTask, ...]:
        clauses: list[str] = []
        parameters: list[object] = []
        if query:
            clauses.append("(prompt LIKE ? OR summary LIKE ?)")
            parameters.extend((f"%{query}%", f"%{query}%"))
        if project_id:
            clauses.append("project_id=?")
            parameters.append(project_id)
        if attention_only:
            clauses.append("status IN ('running','failed')")
        where = "" if not clauses else " WHERE " + " AND ".join(clauses)
        rows = self._database.fetchall(
            "SELECT task_id,workflow_id,prompt,workspace_root,status,created_at,updated_at,"
            "summary,error,continuation_json,parent_task_id,project_id FROM useful_tasks"
            + where + " ORDER BY created_at DESC LIMIT ? OFFSET ?",
            tuple(parameters) + (limit, offset),
        )
        return tuple(self._decode(row) for row in rows)

    def request_document(self, task_id: str) -> dict[str, object]:
        row = self._database.fetchone(
            "SELECT request_json FROM useful_tasks WHERE task_id=?", (task_id,),
        )
        if row is None:
            raise KeyError("useful task was not found")
        value = json.loads(row[0])
        if not isinstance(value, dict):
            raise ValueError("stored useful task request is invalid")
        return value

    def artifact(self, artifact_id: str) -> UsefulArtifact:
        row = self._database.fetchone(
            "SELECT artifact_id,task_id,kind,path,media_type,sha256,size_bytes "
            "FROM useful_artifacts WHERE artifact_id=?", (artifact_id,),
        )
        if row is None:
            raise KeyError("useful artifact was not found")
        return UsefulArtifact(row[0], row[1], row[2], Path(row[3]), row[4], row[5], row[6])

    def _decode(self, row) -> UsefulTask:
        artifact_rows = self._database.fetchall(
            "SELECT artifact_id,task_id,kind,path,media_type,sha256,size_bytes "
            "FROM useful_artifacts WHERE task_id=? ORDER BY artifact_id",
            (row[0],),
        )
        artifacts = tuple(
            UsefulArtifact(
                item[0], item[1], item[2], Path(item[3]), item[4], item[5], item[6],
            )
            for item in artifact_rows
        )
        return UsefulTask(
            row[0], row[1], row[2], Path(row[3]), row[4], row[5], row[6], row[7], row[8],
            artifacts, None if row[9] is None else json.loads(row[9]),
            row[10], row[11],
        )
