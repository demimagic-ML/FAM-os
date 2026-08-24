"""Bounded Shell requests for candidate effects and verification."""

import base64
import hashlib
from dataclasses import dataclass

from fam_os.core.engineering import (
    CandidateArtifact, CandidateOperation, CheckpointDecision,
    EngineeringIncidentStage, GitPublicationApproval,
)


SHELL_ENGINEERING_LOOP_VERSION = "fam.shell.engineering-loop/v1alpha1"


@dataclass(frozen=True, slots=True)
class ShellEngineeringCandidateEditRequest:
    request_id: str
    owner_id: str
    task_id: str
    edit_id: str
    session_id: str
    principal_id: str
    operation: CandidateOperation
    artifact: CandidateArtifact | None
    content_base64: str | None
    confirmed: bool
    contract_version: str = SHELL_ENGINEERING_LOOP_VERSION

    def __post_init__(self) -> None:
        _texts(self, "request_id", "owner_id", "task_id", "edit_id", "session_id", "principal_id")
        _confirmed(self.confirmed)
        content = decode_candidate_edit_content(self)
        if self.artifact is None and content is not None:
            raise ValueError("Shell candidate edit content requires artifact metadata")
        if self.artifact is not None and (
            content is None or len(content) != self.artifact.size_bytes
            or hashlib.sha256(content).hexdigest() != self.artifact.content_sha256
        ):
            raise ValueError("Shell candidate edit content differs from artifact metadata")
        _version(self.contract_version)


@dataclass(frozen=True, slots=True)
class ShellEngineeringCandidateVerificationRequest:
    request_id: str
    owner_id: str
    task_id: str
    verification_id: str
    session_id: str
    principal_id: str
    toolchain: str
    recipe_id: str
    recipe_version: str
    confirmed: bool
    contract_version: str = SHELL_ENGINEERING_LOOP_VERSION

    def __post_init__(self) -> None:
        _texts(self, "request_id", "owner_id", "task_id", "verification_id", "session_id", "principal_id", "toolchain", "recipe_id", "recipe_version")
        _confirmed(self.confirmed)
        _version(self.contract_version)


@dataclass(frozen=True, slots=True)
class ShellEngineeringCandidateReverificationRequest(ShellEngineeringCandidateVerificationRequest):
    """Distinct wire root for independent post-apply verification."""


@dataclass(frozen=True, slots=True)
class ShellEngineeringChangesetPreviewRequest:
    request_id: str
    owner_id: str
    task_id: str
    changeset_id: str
    confirmed: bool
    contract_version: str = SHELL_ENGINEERING_LOOP_VERSION

    def __post_init__(self) -> None:
        _texts(self, "request_id", "owner_id", "task_id", "changeset_id")
        _confirmed(self.confirmed)
        _version(self.contract_version)


@dataclass(frozen=True, slots=True)
class ShellEngineeringChangesetApplyRequest:
    request_id: str
    owner_id: str
    task_id: str
    changeset_id: str
    decision: CheckpointDecision
    session_id: str
    principal_id: str
    confirmed: bool
    contract_version: str = SHELL_ENGINEERING_LOOP_VERSION

    def __post_init__(self) -> None:
        _texts(self, "request_id", "owner_id", "task_id", "changeset_id", "session_id", "principal_id")
        if self.decision.task_id != self.task_id or self.decision.checkpoint_id != self.changeset_id:
            raise ValueError("Shell candidate changeset decision identity is invalid")
        _confirmed(self.confirmed)
        _version(self.contract_version)


@dataclass(frozen=True, slots=True)
class ShellEngineeringPublicationRequest:
    request_id: str
    owner_id: str
    task_id: str
    approval: GitPublicationApproval
    confirmed: bool
    contract_version: str = SHELL_ENGINEERING_LOOP_VERSION

    def __post_init__(self) -> None:
        _texts(self, "request_id", "owner_id", "task_id")
        if self.approval.task_id != self.task_id:
            raise ValueError("Shell Git publication task identity is invalid")
        _confirmed(self.confirmed)
        _version(self.contract_version)


@dataclass(frozen=True, slots=True)
class ShellEngineeringIncidentAdvanceRequest:
    request_id: str
    owner_id: str
    task_id: str
    incident_id: str
    stage: EngineeringIncidentStage
    evidence_id: str
    confirmed: bool
    contract_version: str = SHELL_ENGINEERING_LOOP_VERSION

    def __post_init__(self) -> None:
        _texts(
            self, "request_id", "owner_id", "task_id", "incident_id",
            "evidence_id",
        )
        if not isinstance(self.stage, EngineeringIncidentStage):
            raise ValueError("Shell engineering incident stage is invalid")
        _confirmed(self.confirmed)
        _version(self.contract_version)


def decode_candidate_edit_content(command: ShellEngineeringCandidateEditRequest) -> bytes | None:
    value = command.content_base64
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > 174_764:
        raise ValueError("Shell candidate edit content exceeds its transport bound")
    try:
        content = base64.b64decode(value, validate=True)
    except (ValueError, base64.binascii.Error) as error:
        raise ValueError("Shell candidate edit content is not strict base64") from error
    if len(content) > 131_072:
        raise ValueError("Shell candidate edit content exceeds its decoded bound")
    return content


def _texts(value, *names):
    for name in names:
        if not isinstance(getattr(value, name), str) or not getattr(value, name).strip():
            raise ValueError(f"Shell candidate {name} must be non-empty text")


def _confirmed(value):
    if value is not True:
        raise ValueError("Shell candidate action requires confirmation")


def _version(value):
    if value != SHELL_ENGINEERING_LOOP_VERSION:
        raise ValueError("unsupported Shell engineering loop version")
