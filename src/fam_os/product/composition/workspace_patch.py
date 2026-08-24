"""Previewed, approval-bound, hash-verified owner-workspace text patches."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from fam_os.adapters.linux.scoped_files import ScopedFileAdapter
from fam_os.applications import (
    ActionProposal,
    ActionResult,
    ActionStatus,
    ApplicationFailure,
    ApplicationFailureCategory,
    ApplicationRetryDisposition,
    ConditionEvidence,
    ConditionRequirement,
    ConfirmationPolicy,
    Reversibility,
    WORKSPACE_PATCH_CAPABILITY,
    WORKSPACE_RESTORE_CAPABILITY,
)
from fam_os.applications.payloads import JsonObject
from fam_os.product.composition.workspace_patch_contract import (
    PatchChange,
    PatchRecord,
    RestoreRecord,
    ReversalChange,
    combined_revision,
    decode_before_content,
    encode_token,
    file_preview,
    patch_parameters,
    restore_token,
    target_path,
    workspace_path,
)



class WorkspacePatchProvider:
    def __init__(self, files: ScopedFileAdapter) -> None:
        self._files = files

    def prepare(self, request, workspace: Path) -> ActionProposal:
        if request.capability_id == WORKSPACE_PATCH_CAPABILITY:
            return self._prepare_patch(request, workspace)
        if request.capability_id == WORKSPACE_RESTORE_CAPABILITY:
            return self._prepare_restore(request, workspace)
        raise PermissionError("workspace patch capability is unavailable")

    def execute(self, proposal) -> ActionResult:
        workspace = workspace_path(proposal.request.resource_uri)
        if proposal.request.capability_id == WORKSPACE_PATCH_CAPABILITY:
            return self._execute_patch(proposal, workspace)
        if proposal.request.capability_id == WORKSPACE_RESTORE_CAPABILITY:
            return self._execute_restore(proposal, workspace)
        raise PermissionError("workspace patch capability is unavailable")

    def _prepare_patch(self, request, workspace: Path) -> ActionProposal:
        plan, changes = patch_parameters(request.parameters)
        records = self._current_records(workspace, changes)
        preview: JsonObject = {
            "operation": "apply_workspace_patch",
            "workspace": str(workspace),
            "plan": plan,
            "files": tuple(file_preview(item) for item in records),
        }
        return ActionProposal(
            f"workspace-patch-{request.request_id}", request, preview,
            Reversibility.REVERSIBLE, ConfirmationPolicy.ALWAYS,
            (_condition(
                "workspace.files-match-proposal",
                "Every approved file must match its proposed SHA-256 digest.",
            ),),
            (_condition(
                "workspace.files-unchanged",
                "Every source file must retain its observed SHA-256 digest until execution.",
            ),),
            WORKSPACE_RESTORE_CAPABILITY,
        )

    def _prepare_restore(self, request, workspace: Path) -> ActionProposal:
        changes = restore_token(request.parameters, workspace)
        records = self._restore_records(workspace, changes)
        return ActionProposal(
            f"workspace-restore-{request.request_id}", request,
            {
                "operation": "restore_workspace_patch",
                "workspace": str(workspace),
                "files": tuple(
                    {
                        "path": item["path"],
                        "current_sha256": item["after_sha256"],
                        "restored_sha256": item["before_sha256"],
                    }
                    for item in records
                ),
            },
            Reversibility.IRREVERSIBLE, ConfirmationPolicy.ALWAYS,
            (_condition(
                "workspace.files-restored",
                "Every file must match its pre-patch SHA-256 digest.",
            ),),
            (_condition(
                "workspace.patch-still-current",
                "Every file must still match the completed patch before restoration.",
            ),),
        )

    def _execute_patch(self, proposal, workspace: Path) -> ActionResult:
        plan, changes = patch_parameters(proposal.request.parameters)
        try:
            records = self._current_records(workspace, changes)
        except RuntimeError as error:
            return _failure(
                proposal.proposal_id, ActionStatus.PRECONDITION_FAILED,
                ApplicationFailureCategory.PRECONDITION_FAILED,
                "workspace.patch.precondition_changed", str(error),
            )
        applied: list[PatchRecord] = []
        try:
            for item in records:
                mutation = self._files.apply_write(
                    self._files.prepare_write(
                        f"{proposal.proposal_id}:{item['path']}",
                        item["target"], item["after_content"],
                    ),
                    item["after_content"],
                )
                if mutation.before_sha256 != item["before_sha256"]:
                    raise RuntimeError("workspace patch precondition changed")
                applied.append(item)
        except Exception:
            self._rollback(applied)
            raise
        output_files: list[JsonObject] = []
        for item in records:
            observed = self._files.observe(item["target"])
            if observed.sha256 != item["after_sha256"]:
                raise RuntimeError("workspace patch postcondition failed")
            output_files.append({
                "path": item["path"], "before_sha256": item["before_sha256"],
                "after_sha256": item["after_sha256"],
            })
        token = encode_token(workspace, records)
        return ActionResult(
            proposal.proposal_id, ActionStatus.VERIFIED, _now(),
            (_evidence("workspace.files-match-proposal", True),),
            {
                "operation": "apply_workspace_patch", "plan": plan,
                "files": tuple(output_files),
            },
            before_revision=(
                proposal.request.expected_revision
                or combined_revision(records, "before_sha256")
            ),
            after_revision=combined_revision(records, "after_sha256"),
            reversal_token=token,
        )

    def _execute_restore(self, proposal, workspace: Path) -> ActionResult:
        changes = restore_token(proposal.request.parameters, workspace)
        try:
            records = self._restore_records(workspace, changes)
        except RuntimeError as error:
            return _failure(
                proposal.proposal_id, ActionStatus.PRECONDITION_FAILED,
                ApplicationFailureCategory.PRECONDITION_FAILED,
                "workspace.restore.precondition_changed", str(error),
            )
        for item in records:
            content = item["before_content"]
            self._files.apply_write(
                self._files.prepare_write(
                    f"{proposal.proposal_id}:{item['path']}", item["target"], content,
                ),
                content,
            )
        for item in records:
            if self._files.observe(item["target"]).sha256 != item["before_sha256"]:
                raise RuntimeError("workspace restore postcondition failed")
        return ActionResult(
            proposal.proposal_id, ActionStatus.VERIFIED, _now(),
            (_evidence("workspace.files-restored", True),),
            {
                "operation": "restore_workspace_patch",
                "files": tuple(
                    {"path": item["path"], "sha256": item["before_sha256"]}
                    for item in records
                ),
            },
            before_revision=(
                proposal.request.expected_revision
                or combined_revision(records, "after_sha256")
            ),
            after_revision=combined_revision(records, "before_sha256"),
        )

    def _current_records(
        self, workspace: Path, changes: tuple[PatchChange, ...],
    ) -> list[PatchRecord]:
        records: list[PatchRecord] = []
        for change in changes:
            target = target_path(workspace, change["path"])
            observed = self._files.observe(target, include_content=True)
            if observed.sha256 != change["expected_sha256"]:
                raise RuntimeError(f"observed file changed: {change['path']}")
            before = observed.content or b""
            after = change["content"].encode("utf-8")
            if before == after:
                raise ValueError(f"workspace patch has no change: {change['path']}")
            records.append({
                "path": change["path"], "target": target,
                "before_content": before, "after_content": after,
                "before_sha256": observed.sha256,
                "after_sha256": hashlib.sha256(after).hexdigest(),
            })
        return records

    def _restore_records(
        self, workspace: Path, changes: tuple[ReversalChange, ...],
    ) -> list[RestoreRecord]:
        records: list[RestoreRecord] = []
        for change in changes:
            target = target_path(workspace, change["path"])
            observed = self._files.observe(target)
            if observed.sha256 != change["after_sha256"]:
                raise RuntimeError(f"patched file changed: {change['path']}")
            content = decode_before_content(change)
            records.append({
                "path": change["path"], "target": target,
                "before_content": content,
                "before_sha256": change["before_sha256"],
                "after_sha256": change["after_sha256"],
            })
        return records

    def _rollback(self, applied: list[PatchRecord]) -> None:
        for item in reversed(applied):
            content = item["before_content"]
            self._files.apply_write(
                self._files.prepare_write(
                    f"rollback:{item['path']}", item["target"], content,
                ),
                content,
            )
def _condition(identifier: str, description: str) -> ConditionRequirement:
    return ConditionRequirement(identifier, identifier, description)


def _evidence(identifier: str, passed: bool) -> ConditionEvidence:
    return ConditionEvidence(identifier, identifier, passed, "SHA-256 postcondition observed.")


def _failure(proposal_id, status, category, code, message) -> ActionResult:
    return ActionResult(
        proposal_id, status, _now(), error=ApplicationFailure(
            category, code, message[:500], ApplicationRetryDisposition.AFTER_STATE_CHANGE,
        ),
    )


def _now():
    return datetime.now(timezone.utc)
