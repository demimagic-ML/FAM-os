"""Bind model proposals to trusted candidate state and typed operations."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import mimetypes
from pathlib import PurePosixPath

from fam_os.core.engineering.candidate_generation import (
    GeneratedCandidateOperationKind, GeneratedCandidatePlan,
    generated_candidate_plan_digest,
)
from fam_os.core.engineering.transactions import (
    CandidateArtifact, CandidateContentKind, CandidateEntryKind,
    CandidateOperation, CandidateOperationKind, CandidateWorkspace,
)


@dataclass(frozen=True, slots=True)
class BoundCandidateEdit:
    operation: CandidateOperation
    artifact: CandidateArtifact | None = None
    content: bytes | None = None


def bind_generated_candidate_plan(
    task_id: str, candidate: CandidateWorkspace, plan: GeneratedCandidatePlan,
    *, maximum_operations: int, maximum_content_bytes: int,
) -> tuple[BoundCandidateEdit, ...]:
    """Derive hashes and artifacts from trusted state; model fields stay advisory."""
    if candidate.task_id != task_id:
        raise ValueError("generated plan candidate differs from the task")
    state = {
        item.path: (item.kind, item.content_sha256)
        for item in candidate.entries
    }
    edits: list[BoundCandidateEdit] = []
    plan_digest = generated_candidate_plan_digest(plan)
    for proposed in plan.operations:
        _bind_one(task_id, plan_digest, proposed, state, edits)
    if not edits:
        raise ValueError("generated candidate plan has no effective changes")
    content_bytes = sum(len(item.content or b"") for item in edits)
    if len(edits) > maximum_operations or content_bytes > maximum_content_bytes:
        raise PermissionError("bound generated plan exceeds the task change budget")
    return tuple(edits)


def _bind_one(task_id, plan_digest, proposed, state, edits) -> None:
    kind = proposed.kind
    if kind is GeneratedCandidateOperationKind.CREATE_DIRECTORY:
        _parents(task_id, proposed.path, state, edits)
        _require_absent(proposed.path, state)
        edits.append(_edit(task_id, len(edits), CandidateOperationKind.CREATE_DIRECTORY, proposed.path))
        state[proposed.path] = (CandidateEntryKind.DIRECTORY, None)
        return
    if kind in {
        GeneratedCandidateOperationKind.CREATE_FILE,
        GeneratedCandidateOperationKind.REPLACE_FILE,
    }:
        existing = state.get(proposed.path)
        if kind is GeneratedCandidateOperationKind.CREATE_FILE:
            _require_absent(proposed.path, state)
            operation_kind = CandidateOperationKind.CREATE_FILE
            before = None
        else:
            if existing is None or existing[0] is not CandidateEntryKind.FILE:
                raise RuntimeError("generated replace target is not an existing file")
            operation_kind = CandidateOperationKind.PATCH_FILE
            before = existing[1]
        content = (proposed.content or "").encode("utf-8")
        digest = hashlib.sha256(content).hexdigest()
        if kind is GeneratedCandidateOperationKind.REPLACE_FILE and digest == before:
            return
        _parents(task_id, proposed.path, state, edits)
        artifact_id = _identity("artifact", task_id, len(edits), proposed.path, digest)
        artifact = CandidateArtifact(
            artifact_id, CandidateContentKind.TEXT,
            proposed.media_type or _guessed_media_type(proposed.path), digest,
            len(content), f"untrusted-model-plan:{plan_digest}", proposed.path,
        )
        operation = CandidateOperation(
            _identity("operation", task_id, len(edits), proposed.path, digest),
            operation_kind, proposed.path, before, artifact_id,
        )
        edits.append(BoundCandidateEdit(operation, artifact, content))
        state[proposed.path] = (CandidateEntryKind.FILE, digest)
        return
    if kind is GeneratedCandidateOperationKind.DELETE:
        existing = state.get(proposed.path)
        if existing is None:
            raise RuntimeError("generated delete target is absent")
        if existing[0] is CandidateEntryKind.DIRECTORY and _children(proposed.path, state):
            raise RuntimeError("generated directory deletion requires an empty directory")
        edits.append(_edit(
            task_id, len(edits), CandidateOperationKind.DELETE, proposed.path,
            existing[1],
        ))
        state.pop(proposed.path)
        return
    _bind_move(task_id, proposed.path, proposed.source_path or "", state, edits)


def _bind_move(task_id, target, source, state, edits) -> None:
    existing = state.get(source)
    if existing is None:
        raise RuntimeError("generated move source is absent")
    _require_absent(target, state)
    if target == source or target.startswith(source.rstrip("/") + "/"):
        raise RuntimeError("generated move target enters its source")
    _parents(task_id, target, state, edits)
    operation = CandidateOperation(
        _identity("operation", task_id, len(edits), target, source),
        CandidateOperationKind.MOVE, target, existing[1], None, source,
    )
    edits.append(BoundCandidateEdit(operation))
    moved = {
        path: value for path, value in state.items()
        if path == source or path.startswith(source.rstrip("/") + "/")
    }
    for path in moved:
        state.pop(path)
    for path, value in moved.items():
        suffix = path[len(source):]
        state[target + suffix] = value


def _parents(task_id, path, state, edits) -> None:
    parents = tuple(reversed(PurePosixPath(path).parents[:-1]))
    for parent in parents:
        value = parent.as_posix()
        existing = state.get(value)
        if existing is not None:
            if existing[0] is not CandidateEntryKind.DIRECTORY:
                raise RuntimeError("generated path parent is not a directory")
            continue
        edits.append(_edit(
            task_id, len(edits), CandidateOperationKind.CREATE_DIRECTORY, value,
        ))
        state[value] = (CandidateEntryKind.DIRECTORY, None)


def _edit(task_id, index, kind, path, before=None) -> BoundCandidateEdit:
    operation = CandidateOperation(
        _identity("operation", task_id, index, path, kind.value),
        kind, path, before,
    )
    return BoundCandidateEdit(operation)


def _require_absent(path, state) -> None:
    if path in state:
        raise RuntimeError("generated creation or move target already exists")


def _children(path, state) -> bool:
    prefix = path.rstrip("/") + "/"
    return any(item.startswith(prefix) for item in state)


def _identity(prefix, task_id, index, path, consequence) -> str:
    value = f"{task_id}\0{index}\0{path}\0{consequence}".encode()
    return f"{prefix}-{hashlib.sha256(value).hexdigest()[:32]}"


def _guessed_media_type(path: str) -> str:
    return mimetypes.guess_type(path)[0] or "text/plain"
