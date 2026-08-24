"""Isolated candidate workspace and journaled owner-workspace reconciliation."""

from __future__ import annotations

import json
import os
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from uuid import uuid4

from fam_os.adapters.filesystem.candidate_io import (
    atomic_write, clone_regular, contained, fsync_directory, read_regular,
    reject_tree_symlinks, remove_owned, sha256_bytes,
)
from fam_os.adapters.filesystem.candidate_preview import media_type, render_preview
from fam_os.core.engineering.transactions import (
    CandidateApplyReceipt, CandidateApplyStatus, CandidateArtifact,
    CandidateBaselineEntry, CandidateContentKind, CandidateEntryKind,
    CandidateOperation, CandidateOperationKind, CandidatePreviewItem,
    CandidateTransactionPreview, CandidateWorkspace,
)


_NON_AUTHORITATIVE_DIRECTORIES = frozenset({
    ".git", ".fam", ".hg", ".svn", ".venv", "venv", "node_modules",
    "target", "build", "dist", "__pycache__", ".next", ".cache",
    ".terraform", ".gradle", ".turbo", ".parcel-cache",
    ".mypy_cache", ".nox", ".pytest_cache", ".ruff_cache", ".tox",
    "coverage",
})


class CandidateWorkspaceAdapter:
    def __init__(self, owner_root: Path, transaction_root: Path, *, maximum_files=20_000, maximum_bytes=536_870_912):
        self.owner_root = owner_root.resolve()
        self.transaction_root = transaction_root.resolve()
        self.maximum_files = maximum_files
        self.maximum_bytes = maximum_bytes
        if self.owner_root == self.transaction_root or self.transaction_root.is_relative_to(self.owner_root):
            raise ValueError("transaction storage must be outside the owner workspace")
        reject_tree_symlinks(
            self.owner_root, _NON_AUTHORITATIVE_DIRECTORIES,
        )
        self.transaction_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.transaction_root.is_symlink():
            raise ValueError("transaction root cannot be a symbolic link")

    def create(self, task_id: str, *, now: datetime | None = None) -> CandidateWorkspace:
        entries, tree_digest = self._scan(self.owner_root)
        candidate_id = f"candidate-{uuid4().hex}"
        root = self.transaction_root / candidate_id
        workspace = root / "workspace"
        artifacts = root / "artifacts"
        workspace.mkdir(parents=True, mode=0o700)
        artifacts.mkdir(mode=0o700)
        strategies: set[str] = set()
        for entry in entries:
            source = contained(self.owner_root, entry.path)
            target = contained(workspace, entry.path, missing_leaf=True)
            if entry.kind is CandidateEntryKind.DIRECTORY:
                target.mkdir(exist_ok=False)
            else:
                strategies.add(clone_regular(source, target))
        strategy = "+".join(sorted(strategies)) or "empty_tree"
        return CandidateWorkspace(
            candidate_id, task_id, f"baseline-{uuid4().hex}",
            str(self.owner_root), str(workspace), now or datetime.now(timezone.utc),
            strategy, tree_digest, entries,
        )

    def current_entries(
        self, candidate: CandidateWorkspace,
    ) -> tuple[CandidateBaselineEntry, ...]:
        root = self._candidate_root(candidate)
        entries, _tree_digest = self._scan(root)
        return entries

    def stage_artifact(self, candidate: CandidateWorkspace, artifact: CandidateArtifact, content: bytes) -> None:
        if len(content) != artifact.size_bytes or sha256_bytes(content) != artifact.content_sha256:
            raise ValueError("artifact content does not match declared size and digest")
        if len(content) > self.maximum_bytes:
            raise ValueError("artifact exceeds candidate workspace bound")
        if artifact.content_kind is CandidateContentKind.TEXT:
            content.decode("utf-8")
        artifact_path = self._candidate_root(candidate).parent / "artifacts" / artifact.artifact_id
        if artifact_path.exists():
            existing = read_regular(artifact_path, self.maximum_bytes)
            if existing == content:
                return
            raise FileExistsError("artifact identity is immutable")
        atomic_write(artifact_path, content, 0o400)

    def effect_applied(self, candidate, operation, artifact):
        """Observe an edit postcondition without trusting a caller claim."""
        _reject_metadata(operation.path)
        root = self._candidate_root(candidate)
        target = contained(root, operation.path, missing_leaf=True)
        if operation.kind is CandidateOperationKind.CREATE_DIRECTORY:
            return target.is_dir(), None
        if operation.kind in {
            CandidateOperationKind.CREATE_FILE, CandidateOperationKind.PATCH_FILE,
            CandidateOperationKind.RESTORE,
        }:
            if artifact is None or not target.is_file():
                return False, None
            actual = sha256_bytes(read_regular(target, self.maximum_bytes))
            return actual == artifact.content_sha256, actual
        if operation.kind is CandidateOperationKind.DELETE:
            return not target.exists(), None
        if operation.kind is CandidateOperationKind.MOVE:
            source = contained(root, operation.source_path or "", missing_leaf=True)
            if source.exists() or not target.exists():
                return False, None
            if target.is_file():
                actual = sha256_bytes(read_regular(target, self.maximum_bytes))
                return actual == operation.expected_before_sha256, actual
            return target.is_dir() and operation.expected_before_sha256 is None, None
        if not target.is_file():
            return False, None
        actual = sha256_bytes(read_regular(target, self.maximum_bytes))
        executable = bool(target.stat(follow_symlinks=False).st_mode & 0o111)
        return executable is operation.executable, actual

    def execute(self, candidate: CandidateWorkspace, operation: CandidateOperation, artifacts: dict[str, CandidateArtifact]) -> None:
        _reject_metadata(operation.path)
        if operation.source_path is not None:
            _reject_metadata(operation.source_path)
        root = self._candidate_root(candidate)
        target = contained(root, operation.path, missing_leaf=True)
        kind = operation.kind
        if kind is not CandidateOperationKind.MOVE:
            self._check_expected(target, operation.expected_before_sha256)
        if kind is CandidateOperationKind.CREATE_DIRECTORY:
            target.mkdir()
        elif kind in {CandidateOperationKind.CREATE_FILE, CandidateOperationKind.PATCH_FILE, CandidateOperationKind.RESTORE}:
            artifact = artifacts.get(operation.artifact_id or "")
            if artifact is None:
                raise ValueError("operation artifact is unavailable")
            content = read_regular(root.parent / "artifacts" / artifact.artifact_id, self.maximum_bytes)
            if sha256_bytes(content) != artifact.content_sha256:
                raise RuntimeError("staged artifact digest changed")
            mode = stat.S_IMODE(target.stat().st_mode) if target.exists() else 0o600
            atomic_write(target, content, mode)
        elif kind is CandidateOperationKind.MOVE:
            source = contained(root, operation.source_path or "")
            self._check_expected(source, operation.expected_before_sha256)
            if target.exists():
                raise FileExistsError("move destination already exists")
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(source, target)
        elif kind is CandidateOperationKind.DELETE:
            remove_owned(target)
        elif kind is CandidateOperationKind.SET_EXECUTABLE:
            mode = stat.S_IMODE(target.stat(follow_symlinks=False).st_mode)
            os.chmod(target, mode | 0o100 if operation.executable else mode & ~0o111)
        else:
            raise ValueError("unsupported candidate operation")

    def preview(self, candidate: CandidateWorkspace, transaction_id: str, operations: tuple[CandidateOperation, ...], artifacts: dict[str, CandidateArtifact], verification_summary: str, *, verification_evidence_ids: tuple[str, ...], now=None) -> CandidateTransactionPreview:
        baseline = {item.path: item for item in candidate.entries}
        root = self._candidate_root(candidate)
        items: list[CandidatePreviewItem] = []
        for operation in operations:
            _reject_metadata(operation.path)
            if operation.source_path is not None:
                _reject_metadata(operation.source_path)
            before = baseline.get(operation.source_path or operation.path)
            target = contained(root, operation.path, missing_leaf=True)
            after_content = read_regular(target, self.maximum_bytes) if target.is_file() else None
            artifact = artifacts.get(operation.artifact_id or "")
            detected_media_type = artifact.media_type if artifact else media_type(operation.path, after_content)
            before_content = None
            source_path = operation.source_path or operation.path
            owner_source = contained(self.owner_root, source_path, missing_leaf=True)
            if owner_source.is_file():
                before_content = read_regular(owner_source, self.maximum_bytes)
            rendered, risks = render_preview(before_content, after_content, detected_media_type, operation)
            if target.is_file():
                before_executable = bool(
                    before is not None
                    and before.kind is CandidateEntryKind.FILE
                    and before.executable
                )
                after_executable = bool(
                    target.stat(follow_symlinks=False).st_mode & 0o111
                )
                if before_executable != after_executable:
                    mode_line = "\nexecutable mode: " + (
                        "enabled" if after_executable else "disabled"
                    )
                    rendered = rendered[:65_536 - len(mode_line)] + mode_line
                    risks = tuple(dict.fromkeys((*risks, "set_executable")))
            items.append(CandidatePreviewItem(
                operation.path, operation.kind,
                before.content_sha256 if before and before.kind is CandidateEntryKind.FILE else None,
                sha256_bytes(after_content) if after_content is not None else None,
                detected_media_type, (len(after_content) if after_content else 0) - (before.size_bytes if before else 0),
                rendered, risks,
            ))
        return CandidateTransactionPreview(
            transaction_id, candidate.candidate_id, candidate.baseline_tree_sha256,
            now or datetime.now(timezone.utc), tuple(items),
            verification_evidence_ids, verification_summary,
            "Journaled apply restores only FAM-owned changes whose post-state is unchanged.",
        )

    def reconcile(self, candidate: CandidateWorkspace, preview: CandidateTransactionPreview, operations: tuple[CandidateOperation, ...], *, approved: bool, fault_after: int | None = None, after_apply: Callable[[int, Path], None] | None = None, now=None) -> CandidateApplyReceipt:
        if not approved or preview.candidate_id != candidate.candidate_id:
            raise PermissionError("candidate reconciliation requires matching owner approval")
        self._preflight(operations)
        root = self._candidate_root(candidate)
        journal_path = root.parent / "apply-journal.json"
        backup_root = root.parent / "backups"
        backup_root.mkdir(exist_ok=False)
        records = [self._backup(operation, backup_root) for operation in operations]
        self._write_journal(journal_path, preview.transaction_id, "applying", records)
        applied: list[dict] = []
        try:
            for index, (operation, record) in enumerate(zip(operations, records, strict=True), 1):
                self._apply_one(root, operation)
                record["after"] = self._state(operation.path)
                record["applied"] = True
                applied.append(record)
                self._write_journal(journal_path, preview.transaction_id, "applying", records)
                if after_apply is not None:
                    after_apply(index, self.owner_root / operation.path)
                if fault_after == index:
                    raise RuntimeError("injected interrupted apply")
        except Exception as error:
            preserved, complete = self._rollback(records, backup_root)
            status = CandidateApplyStatus.ROLLED_BACK if complete else CandidateApplyStatus.RECOVERY_REQUIRED
            self._write_journal(journal_path, preview.transaction_id, status.value, records)
            return self._receipt(candidate, preview, status, tuple(item["path"] for item in applied), preserved, journal_path, complete, str(error), now)
        self._write_journal(journal_path, preview.transaction_id, "applied", records)
        return self._receipt(candidate, preview, CandidateApplyStatus.APPLIED, tuple(item["path"] for item in records), (), journal_path, False, "candidate transaction applied", now)

    def recover(self, candidate: CandidateWorkspace, *, now=None) -> CandidateApplyReceipt:
        root = self._candidate_root(candidate)
        journal_path = root.parent / "apply-journal.json"
        document = json.loads(read_regular(journal_path, self.maximum_bytes))
        records = document["records"]
        if document["state"] == CandidateApplyStatus.ROLLED_BACK.value:
            preserved = self._rollback_drift(records)
            complete = not preserved
        else:
            preserved, complete = self._rollback(records, root.parent / "backups")
        status = CandidateApplyStatus.ROLLED_BACK if complete else CandidateApplyStatus.RECOVERY_REQUIRED
        self._write_journal(journal_path, document["transaction_id"], status.value, records)
        preview = CandidateTransactionPreview(document["transaction_id"], candidate.candidate_id, candidate.baseline_tree_sha256, now or datetime.now(timezone.utc), (CandidatePreviewItem(records[0]["path"], CandidateOperationKind(records[0]["kind"]), None, None, None, 0, "recovery", ("interrupted_apply",)),), ("journal-recovery",), "recovery", "scoped rollback")
        return self._receipt(candidate, preview, status, (), preserved, journal_path, complete, "interrupted transaction recovered", now)

    def _rollback_drift(self, records) -> tuple[str, ...]:
        """Recognize a completed rollback without replaying its filesystem effects."""
        drifted = []
        for record in records:
            if not record.get("applied"):
                continue
            source = record.get("source_path") or record["path"]
            if self._state(source) != record.get("before"):
                drifted.append(source)
                continue
            if record.get("source_path") and self._state(record["path"])["kind"] != "missing":
                drifted.append(record["path"])
        return tuple(dict.fromkeys(drifted))

    def _scan(self, root):
        # Verifiers run against the candidate and may create caches such as
        # __pycache__ or .pytest_cache.  These directories are excluded from
        # the owner baseline, so they must remain non-authoritative when the
        # candidate is scanned for the final changeset as well.
        exclusions = _NON_AUTHORITATIVE_DIRECTORIES
        reject_tree_symlinks(root, exclusions)
        entries: list[CandidateBaselineEntry] = []
        total = 0
        for current, directories, files in os.walk(root, followlinks=False):
            directories[:] = sorted(
                name for name in directories if name not in exclusions
            )
            current_path = Path(current)
            for name in directories:
                relative = (current_path / name).relative_to(root).as_posix()
                entries.append(CandidateBaselineEntry(
                    relative, CandidateEntryKind.DIRECTORY, None, 0, False,
                ))
                if len(entries) > self.maximum_files:
                    raise ValueError("workspace exceeds candidate bounds")
            for name in sorted(files):
                path = current_path / name
                relative = path.relative_to(root).as_posix()
                content = read_regular(path, self.maximum_bytes)
                total += len(content)
                entries.append(CandidateBaselineEntry(relative, CandidateEntryKind.FILE, sha256_bytes(content), len(content), bool(path.stat().st_mode & 0o111)))
                if len(entries) > self.maximum_files or total > self.maximum_bytes:
                    raise ValueError("workspace exceeds candidate bounds")
        entries.sort(key=lambda item: item.path)
        wire = "\n".join(f"{item.path}:{item.kind}:{item.content_sha256}:{item.executable}" for item in entries).encode()
        return tuple(entries), sha256_bytes(wire)

    def _candidate_root(self, candidate):
        root = Path(candidate.candidate_workspace)
        expected = self.transaction_root / candidate.candidate_id / "workspace"
        if root != expected or not root.is_dir() or root.is_symlink():
            raise PermissionError("candidate workspace identity is invalid")
        return root

    def _check_expected(self, path, expected):
        actual = sha256_bytes(read_regular(path, self.maximum_bytes)) if path.is_file() else None
        if actual != expected:
            raise RuntimeError("candidate operation baseline is stale")

    def _preflight(self, operations):
        reject_tree_symlinks(
            self.owner_root, _NON_AUTHORITATIVE_DIRECTORIES,
        )
        for operation in operations:
            _reject_metadata(operation.path)
            if operation.source_path is not None:
                _reject_metadata(operation.source_path)
            path = contained(self.owner_root, operation.source_path or operation.path, missing_leaf=True)
            self._check_expected(path, operation.expected_before_sha256)
            if operation.kind in {CandidateOperationKind.CREATE_FILE, CandidateOperationKind.CREATE_DIRECTORY, CandidateOperationKind.MOVE}:
                destination = contained(self.owner_root, operation.path, missing_leaf=True)
                if operation.kind is not CandidateOperationKind.MOVE and operation.expected_before_sha256 is None and destination.exists():
                    raise RuntimeError("owner workspace creation target changed")
                if operation.kind is CandidateOperationKind.MOVE and destination.exists():
                    raise RuntimeError("owner workspace move target changed")

    def _backup(self, operation, backup_root):
        source_path = operation.source_path or operation.path
        source = contained(self.owner_root, source_path, missing_leaf=True)
        backup = backup_root / operation.operation_id
        existed = source.exists()
        if existed:
            if source.is_dir():
                backup.mkdir()
            else:
                clone_regular(source, backup)
        return {"operation_id": operation.operation_id, "kind": operation.kind.value, "path": operation.path, "source_path": operation.source_path, "existed": existed, "before": self._state(source_path), "after": None, "applied": False}

    def _apply_one(self, candidate_root, operation):
        target = contained(self.owner_root, operation.path, missing_leaf=True)
        candidate = contained(candidate_root, operation.path, missing_leaf=True)
        if operation.kind is CandidateOperationKind.CREATE_DIRECTORY:
            target.mkdir()
        elif operation.kind in {CandidateOperationKind.CREATE_FILE, CandidateOperationKind.PATCH_FILE, CandidateOperationKind.RESTORE}:
            mode = stat.S_IMODE(candidate.stat().st_mode)
            atomic_write(target, read_regular(candidate, self.maximum_bytes), mode)
        elif operation.kind is CandidateOperationKind.MOVE:
            source = contained(self.owner_root, operation.source_path or "")
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(source, target)
        elif operation.kind is CandidateOperationKind.DELETE:
            remove_owned(target)
        elif operation.kind is CandidateOperationKind.SET_EXECUTABLE:
            os.chmod(target, stat.S_IMODE(candidate.stat().st_mode))
        fsync_directory(target.parent)

    def _rollback(self, records, backup_root):
        preserved: list[str] = []
        complete = True
        for record in reversed(records):
            if not record.get("applied"):
                continue
            if self._state(record["path"]) != record.get("after"):
                preserved.append(record["path"])
                complete = False
                continue
            target = contained(self.owner_root, record["path"], missing_leaf=True)
            source_path = record.get("source_path") or record["path"]
            restore_target = contained(self.owner_root, source_path, missing_leaf=True)
            if target.exists() and target != restore_target:
                remove_owned(target)
            backup = backup_root / record["operation_id"]
            if record["existed"]:
                if backup.is_dir():
                    restore_target.mkdir(exist_ok=True)
                else:
                    atomic_write(restore_target, read_regular(backup, self.maximum_bytes), stat.S_IMODE(backup.stat().st_mode))
            elif target.exists():
                remove_owned(target)
        return tuple(preserved), complete

    def _state(self, relative):
        path = contained(self.owner_root, relative, missing_leaf=True)
        if not path.exists():
            return {"kind": "missing"}
        if path.is_dir():
            return {"kind": "directory"}
        content = read_regular(path, self.maximum_bytes)
        return {"kind": "file", "sha256": sha256_bytes(content), "mode": stat.S_IMODE(path.stat().st_mode)}

    def _write_journal(self, path, transaction_id, state, records):
        content = json.dumps({"version": 1, "transaction_id": transaction_id, "state": state, "records": records}, sort_keys=True, separators=(",", ":")).encode()
        atomic_write(path, content, 0o600)

    def _receipt(self, candidate, preview, status, applied, preserved, journal, complete, message, now):
        return CandidateApplyReceipt(preview.transaction_id, candidate.candidate_id, now or datetime.now(timezone.utc), status, applied, preserved, sha256_bytes(read_regular(journal, self.maximum_bytes)), complete, message)


def _reject_metadata(relative: str) -> None:
    if {".git", ".fam"}.intersection(Path(relative).parts):
        raise PermissionError("candidate operation cannot access product metadata")
