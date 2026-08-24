"""Durable user-facing task and artifact contracts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class UsefulArtifact:
    artifact_id: str
    task_id: str
    kind: str
    path: Path
    media_type: str
    sha256: str
    size_bytes: int

    def to_dict(self) -> dict[str, object]:
        return {
            "artifact_id": self.artifact_id,
            "task_id": self.task_id,
            "kind": self.kind,
            "path": str(self.path),
            "media_type": self.media_type,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
        }


@dataclass(frozen=True, slots=True)
class UsefulTask:
    task_id: str
    workflow_id: str
    prompt: str
    workspace_root: Path
    status: str
    created_at: str
    updated_at: str
    summary: str | None = None
    error: str | None = None
    artifacts: tuple[UsefulArtifact, ...] = ()
    continuation: dict[str, object] | None = None
    parent_task_id: str | None = None
    project_id: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "task_id": self.task_id,
            "workflow_id": self.workflow_id,
            "prompt": self.prompt,
            "workspace_root": str(self.workspace_root),
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "summary": self.summary,
            "error": self.error,
            "artifacts": [item.to_dict() for item in self.artifacts],
            "continuation": self.continuation,
            "parent_task_id": self.parent_task_id,
            "project_id": self.project_id,
        }
