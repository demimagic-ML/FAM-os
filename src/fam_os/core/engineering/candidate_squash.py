"""Deterministic final candidate diff derived from authorized edit history."""

import hashlib
import mimetypes

from fam_os.core.engineering.candidate_edit import (
    CandidateEditRecord, CandidateEditStatus,
)
from fam_os.core.engineering.transactions import (
    CandidateArtifact, CandidateBaselineEntry, CandidateContentKind,
    CandidateEntryKind, CandidateOperation, CandidateOperationKind,
    CandidateWorkspace,
)


def squash_candidate_edits(
    task_id: str,
    candidate: CandidateWorkspace,
    current_entries: tuple[CandidateBaselineEntry, ...],
    edits: tuple[CandidateEditRecord, ...],
    *,
    maximum_operations: int,
    maximum_content_bytes: int,
    authorized_external_paths: tuple[str, ...] = (),
) -> tuple[tuple[CandidateOperation, ...], tuple[CandidateArtifact, ...]]:
    """Return one owner-baseline operation per final changed path."""
    if candidate.task_id != task_id:
        raise ValueError("candidate squash task differs")
    applied = tuple(item for item in edits if item.status is CandidateEditStatus.APPLIED)
    allowed = {
        path
        for item in applied
        for path in (item.operation.path, item.operation.source_path)
        if path is not None
    }
    allowed.update(authorized_external_paths)
    baseline = {item.path: item for item in candidate.entries}
    current = {item.path: item for item in current_entries}
    if any(
        path in baseline and path in current
        and baseline[path].kind is not current[path].kind
        for path in set(baseline) | set(current)
    ):
        raise RuntimeError("candidate final state cannot change an entry kind in place")
    changed = tuple(sorted(
        path for path in set(baseline) | set(current)
        if _different(baseline.get(path), current.get(path))
    ))
    if not changed:
        raise ValueError("candidate squash has no final changes")
    unauthorized = tuple(path for path in changed if path not in allowed)
    if unauthorized:
        raise PermissionError("candidate final state contains an unauthorized path")

    operations: list[CandidateOperation] = []
    artifacts: list[CandidateArtifact] = []
    created_directories = sorted(
        (
            path for path in changed
            if path not in baseline
            and current[path].kind is CandidateEntryKind.DIRECTORY
        ),
        key=lambda path: (path.count("/"), path),
    )
    for path in created_directories:
        operations.append(_operation(task_id, path, "directory-create",
                                     CandidateOperationKind.CREATE_DIRECTORY))

    for path in changed:
        before, after = baseline.get(path), current.get(path)
        if after is None or after.kind is CandidateEntryKind.DIRECTORY:
            continue
        if before is not None and before.content_sha256 == after.content_sha256:
            operations.append(CandidateOperation(
                _identity(task_id, path, "mode", str(after.executable)),
                CandidateOperationKind.SET_EXECUTABLE, path,
                before.content_sha256, executable=after.executable,
            ))
            continue
        artifact = _artifact(task_id, path, after)
        artifacts.append(artifact)
        operations.append(CandidateOperation(
            _identity(task_id, path, "content", after.content_sha256 or ""),
            CandidateOperationKind.CREATE_FILE if before is None
            else CandidateOperationKind.PATCH_FILE,
            path, None if before is None else before.content_sha256,
            artifact.artifact_id,
        ))

    deleted = sorted(
        (path for path in changed if path not in current),
        key=lambda path: (
            baseline[path].kind is CandidateEntryKind.DIRECTORY,
            -path.count("/"), path,
        ),
    )
    for path in deleted:
        before = baseline[path]
        operations.append(_operation(
            task_id, path, "delete", CandidateOperationKind.DELETE,
            before.content_sha256,
        ))

    content_bytes = sum(item.size_bytes for item in artifacts)
    if (
        not operations
        or len(operations) > maximum_operations
        or content_bytes > maximum_content_bytes
    ):
        raise PermissionError("candidate final state exceeds changeset bounds")
    paths = tuple(item.path for item in operations)
    if len(paths) != len(set(paths)):
        raise RuntimeError("candidate squash produced duplicate final paths")
    return tuple(operations), tuple(artifacts)


def _different(before, after) -> bool:
    if before is None or after is None:
        return before != after
    return (
        before.kind is not after.kind
        or before.content_sha256 != after.content_sha256
        or before.executable != after.executable
    )


def _operation(task_id, path, consequence, kind, before=None):
    return CandidateOperation(
        _identity(task_id, path, consequence, before or ""),
        kind, path, before,
    )


def _artifact(task_id, path, entry):
    media_type = mimetypes.guess_type(path)[0] or "application/octet-stream"
    content_kind = (
        CandidateContentKind.TEXT
        if media_type.startswith("text/") or path.endswith((
            ".py", ".js", ".ts", ".tsx", ".jsx", ".rs", ".go", ".java",
            ".c", ".h", ".cpp", ".hpp", ".md", ".json", ".yaml", ".yml",
            ".toml", ".sh", ".css", ".html", ".sql",
        ))
        else CandidateContentKind.BINARY
    )
    artifact_id = _identity(task_id, path, "artifact", entry.content_sha256 or "")
    return CandidateArtifact(
        artifact_id, content_kind, media_type,
        entry.content_sha256 or "", entry.size_bytes,
        "trusted-candidate-final-state", path,
    )


def _identity(task_id, path, *values):
    digest = hashlib.sha256(
        "\0".join((task_id, path, *values)).encode("utf-8")
    ).hexdigest()[:32]
    return f"candidate-final-{digest}"
