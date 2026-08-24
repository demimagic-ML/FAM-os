"""Fail-closed live verification of VS Code action conditions."""

import hashlib
import os
import stat
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit
from uuid import uuid4

from fam_os.applications import (
    ConditionEvidence,
    ObservationRequest,
    ObservationStatus,
)
from fam_os.product.composition.owner_filesystem import (
    INSPECT_CAPABILITY, directory_token,
)


class LiveApplicationConditionVerifier:
    """Re-observe editor state instead of trusting action output alone."""

    _ALLOWED = frozenset({
        "sha256", "vscode.document-version", "file.sha256",
        "vscode.document-saved", "process.exit-zero",
        "accessibility.action.poststate", "screen.input.postframe",
        "directory.absent", "directory.exists-empty", "directory.reversal-ready",
        "workspace.files-unchanged", "workspace.files-match-proposal",
        "workspace.patch-still-current", "workspace.files-restored",
    })

    def __init__(self, provider) -> None:
        self._provider = provider

    def verify(self, requirement, proposal, provider_result=None):
        if requirement.verifier_id not in self._ALLOWED:
            return self._failed(requirement, "Verifier is not activated.")
        if requirement.verifier_id == "file.sha256":
            return self._file_hash(requirement, proposal, provider_result)
        if requirement.verifier_id == "process.exit-zero":
            return self._process_exit(requirement, provider_result)
        if requirement.verifier_id.startswith("directory."):
            return self._directory(requirement, proposal)
        if requirement.verifier_id.startswith("workspace."):
            return self._workspace(requirement, proposal, provider_result)
        if requirement.verifier_id == "accessibility.action.poststate":
            return self._accessibility_poststate(requirement, proposal, provider_result)
        if requirement.verifier_id == "screen.input.postframe":
            return self._screen_postframe(requirement, proposal, provider_result)
        expected = (
            proposal.request.expected_revision
            if provider_result is None else provider_result.after_revision
        )
        if expected is None:
            return self._failed(requirement, "Expected editor revision is absent.")
        observed = self._provider.observe(ObservationRequest(
            str(uuid4()), proposal.request.instance_id, "vscode.editor.active",
            proposal.request.permission_grant_id, {}, proposal.request.resource_uri,
        ))
        provider_evidence = () if provider_result is None else (
            item for item in provider_result.postcondition_evidence
            if item.condition_id == requirement.condition_id
            and item.verifier_id == requirement.verifier_id
        )
        provider_passed = provider_result is None or any(
            item.passed for item in provider_evidence
        )
        passed = (
            observed.status is ObservationStatus.OBSERVED
            and observed.revision == expected
            and provider_passed
        )
        details = observed.revision or "Editor state was unavailable."
        return ConditionEvidence(
            requirement.condition_id, requirement.verifier_id, passed, details,
        )

    def _file_hash(self, requirement, proposal, provider_result):
        if provider_result is None:
            return self._failed(requirement, "Disk hash is a postcondition only.")
        expected = provider_result.output.get("disk_sha256")
        try:
            path = _file_path(proposal.request.resource_uri)
            observed = _sha256_regular(path)
        except (OSError, TypeError, ValueError):
            return self._failed(requirement, "Scoped disk bytes were unavailable.")
        passed = isinstance(expected, str) and expected == observed
        return ConditionEvidence(
            requirement.condition_id, requirement.verifier_id, passed,
            f"sha256:{observed}",
        )

    def _process_exit(self, requirement, provider_result):
        if provider_result is None:
            return self._failed(requirement, "Command result is absent.")
        matching = tuple(
            item for item in provider_result.postcondition_evidence
            if item.condition_id == requirement.condition_id
            and item.verifier_id == requirement.verifier_id
        )
        passed = (
            provider_result.output.get("exit_code") == 0
            and provider_result.output.get("timed_out") is False
            and provider_result.output.get("output_limited") is False
            and any(item.passed for item in matching)
        )
        return ConditionEvidence(
            requirement.condition_id, requirement.verifier_id, passed,
            "Core-owned bounded process exit evidence passed."
            if passed else "Bounded process evidence did not pass.",
        )

    def _accessibility_poststate(self, requirement, proposal, provider_result):
        expected = _provider_output(provider_result, "after_fingerprint")
        if not isinstance(expected, str) or not _provider_passed(
            provider_result, requirement,
        ):
            return self._failed(requirement, "Accessibility provider evidence failed.")
        observed = self._observe(
            proposal, "linux.accessibility.observe_tree",
        )
        fingerprints = _accessibility_fingerprints(observed.payload)
        passed = observed.status is ObservationStatus.OBSERVED and expected in fingerprints
        return ConditionEvidence(
            requirement.condition_id, requirement.verifier_id, passed,
            "Independent accessibility poststate matched."
            if passed else "Independent accessibility poststate did not match.",
        )

    def _screen_postframe(self, requirement, proposal, provider_result):
        expected = _provider_output(provider_result, "after_scene_id")
        if not isinstance(expected, str) or not _provider_passed(
            provider_result, requirement,
        ):
            return self._failed(requirement, "Screen provider evidence failed.")
        observed = self._observe(proposal, "linux.screen.observe_active_window")
        passed = (
            observed.status is ObservationStatus.OBSERVED
            and observed.revision == expected
        )
        return ConditionEvidence(
            requirement.condition_id, requirement.verifier_id, passed,
            "Independent screen postframe matched."
            if passed else "Independent screen postframe did not match.",
        )

    def _directory(self, requirement, proposal):
        observed = self._provider.observe(ObservationRequest(
            str(uuid4()), proposal.request.instance_id, INSPECT_CAPABILITY,
            proposal.request.permission_grant_id, {}, proposal.request.resource_uri,
        ))
        payload = observed.payload
        passed = False
        if observed.status is ObservationStatus.OBSERVED:
            if requirement.verifier_id == "directory.absent":
                passed = payload.get("exists") is False
            elif requirement.verifier_id == "directory.exists-empty":
                passed = (
                    payload.get("exists") is True and payload.get("empty") is True
                )
            else:
                try:
                    device, inode = directory_token(
                        proposal.request.parameters.get("reversal_token"),
                    )
                except (TypeError, ValueError):
                    device, inode = None, None
                passed = (
                    payload.get("exists") is True
                    and payload.get("empty") is True
                    and payload.get("device") == device
                    and payload.get("inode") == inode
                )
        return ConditionEvidence(
            requirement.condition_id, requirement.verifier_id, passed,
            "Independent scoped directory observation passed."
            if passed else "Independent scoped directory observation failed.",
        )

    def _workspace(self, requirement, proposal, provider_result):
        source = (
            proposal.preview.get("files")
            if provider_result is None else provider_result.output.get("files")
        )
        if not isinstance(source, (list, tuple)) or not source:
            return self._failed(requirement, "Workspace file evidence is absent.")
        expected_key = {
            "workspace.files-unchanged": "before_sha256",
            "workspace.patch-still-current": "current_sha256",
            "workspace.files-match-proposal": "after_sha256",
            "workspace.files-restored": "sha256",
        }[requirement.verifier_id]
        try:
            workspace = _file_path(proposal.request.resource_uri)
            passed = all(
                _workspace_hash(workspace, item) == item.get(expected_key)
                for item in source
                if isinstance(item, Mapping)
            ) and all(isinstance(item, Mapping) for item in source)
        except (OSError, TypeError, ValueError):
            passed = False
        if provider_result is not None:
            passed = passed and _provider_passed(
                provider_result, requirement,
            )
        return ConditionEvidence(
            requirement.condition_id, requirement.verifier_id, passed,
            "Independent workspace SHA-256 observation passed."
            if passed else "Independent workspace SHA-256 observation failed.",
        )

    def _observe(self, proposal, capability_id):
        return self._provider.observe(ObservationRequest(
            str(uuid4()), proposal.request.instance_id, capability_id,
            proposal.request.permission_grant_id, {}, proposal.request.resource_uri,
        ))

    @staticmethod
    def _failed(requirement, details):
        return ConditionEvidence(
            requirement.condition_id, requirement.verifier_id, False, details,
        )


def _file_path(resource_uri: str | None) -> Path:
    if resource_uri is None:
        raise ValueError("file resource is absent")
    parsed = urlsplit(resource_uri)
    if parsed.scheme != "file" or parsed.netloc not in {"", "localhost"}:
        raise ValueError("resource is not a local file")
    path = Path(unquote(parsed.path))
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("file path is not canonical")
    return path


def _sha256_regular(path: Path) -> str:
    descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    digest = hashlib.sha256()
    total = 0
    try:
        details = os.fstat(descriptor)
        if not stat.S_ISREG(details.st_mode):
            raise ValueError("resource is not a regular file")
        while True:
            chunk = os.read(descriptor, 65_536)
            if not chunk:
                return digest.hexdigest()
            total += len(chunk)
            if total > 16_777_216:
                raise ValueError("file exceeds postcondition verifier limit")
            digest.update(chunk)
    finally:
        os.close(descriptor)


def _workspace_hash(workspace: Path, item: Mapping) -> str:
    relative = item.get("path")
    if not isinstance(relative, str):
        raise ValueError("workspace evidence path is invalid")
    path = PurePosixPath(relative)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("workspace evidence path is invalid")
    target = workspace.joinpath(*path.parts)
    if not target.is_relative_to(workspace):
        raise ValueError("workspace evidence path escaped scope")
    return _sha256_regular(target)


def _provider_output(provider_result, name: str):
    if provider_result is None:
        return None
    return provider_result.output.get(name)


def _provider_passed(provider_result, requirement) -> bool:
    if provider_result is None:
        return False
    return any(
        item.passed
        and item.condition_id == requirement.condition_id
        and item.verifier_id == requirement.verifier_id
        for item in provider_result.postcondition_evidence
    )


def _accessibility_fingerprints(payload) -> set[str]:
    if not isinstance(payload, Mapping):
        return set()
    nodes = payload.get("nodes")
    if not isinstance(nodes, (list, tuple)):
        return set()
    values = set()
    for node in nodes:
        if not isinstance(node, Mapping):
            continue
        reference = node.get("reference")
        if isinstance(reference, Mapping):
            fingerprint = reference.get("fingerprint")
            if isinstance(fingerprint, str):
                values.add(fingerprint)
    return values
