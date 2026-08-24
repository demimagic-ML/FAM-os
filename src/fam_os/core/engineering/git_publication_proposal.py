"""Exact effect-free Git publication observations and owner proposal."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum

from fam_os.core.engineering._validation import aware, digest, text, texts
from fam_os.core.engineering.authority import EngineeringAuthority
from fam_os.core.engineering.git_delivery import (
    GitPublicationApproval, GitPublicationKind,
)
from fam_os.core.engineering.grants import (
    EngineeringAuthorityGrant, EngineeringGrantScopeKind,
    SecretExposurePolicy,
)
from fam_os.core.engineering.version import ENGINEERING_CONTRACT_VERSION


_REF = re.compile(r"^refs/heads/[A-Za-z0-9][A-Za-z0-9._/-]{0,190}$")
_SECRET_REF = re.compile(r"^secret\.[A-Za-z0-9][A-Za-z0-9._:/-]{0,191}$")


@dataclass(frozen=True, slots=True)
class GitPublicationLocalState:
    task_id: str
    repository_root: str
    remote_name: str
    remote_url_sha256: str
    source_ref: str
    proposed_new_object_id: str
    commit_object_ids: tuple[str, ...]
    complete_diff_sha256: str
    observed_at: datetime
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in ("task_id", "repository_root", "remote_name", "source_ref"):
            text(getattr(self, name), name)
        for name in (
            "remote_url_sha256", "complete_diff_sha256",
        ):
            digest(getattr(self, name), name, required=True)
        _object_id(self.proposed_new_object_id, "proposed_new_object_id")
        _ref(self.source_ref)
        _object_ids(self.commit_object_ids)
        aware(self.observed_at, "observed_at")
        _version(self.contract_version)


@dataclass(frozen=True, slots=True)
class GitRemoteRefObservationRequest:
    request_id: str
    task_id: str
    repository_root: str
    remote_name: str
    remote_url_sha256: str
    target_ref: str
    proposed_new_object_id: str
    credential_ref: str
    requested_at: datetime
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in (
            "request_id", "task_id", "repository_root", "remote_name",
            "target_ref", "credential_ref",
        ):
            text(getattr(self, name), name)
        digest(self.remote_url_sha256, "remote_url_sha256", required=True)
        _object_id(self.proposed_new_object_id, "proposed_new_object_id")
        _ref(self.target_ref)
        _secret_ref(self.credential_ref)
        aware(self.requested_at, "requested_at")
        _version(self.contract_version)


@dataclass(frozen=True, slots=True)
class GitRemoteRefObservation:
    observation_id: str
    request_id: str
    provider_id: str
    remote_name: str
    remote_url_sha256: str
    target_ref: str
    observed_object_id: str | None
    observed_at: datetime
    provider_evidence_sha256: str
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in (
            "observation_id", "request_id", "provider_id", "remote_name",
            "target_ref",
        ):
            text(getattr(self, name), name)
        digest(self.remote_url_sha256, "remote_url_sha256", required=True)
        _ref(self.target_ref)
        if self.observed_object_id is not None:
            _object_id(self.observed_object_id, "observed_object_id")
        aware(self.observed_at, "observed_at")
        digest(
            self.provider_evidence_sha256, "provider_evidence_sha256",
            required=True,
        )
        _version(self.contract_version)


@dataclass(frozen=True, slots=True)
class GitPublicationProposal:
    proposal_id: str
    task_id: str
    grant: EngineeringAuthorityGrant
    kind: GitPublicationKind
    repository_root: str
    remote_name: str
    remote_url_sha256: str
    source_ref: str
    target_ref: str
    expected_old_object_id: str | None
    proposed_new_object_id: str
    commit_object_ids: tuple[str, ...]
    complete_diff_sha256: str
    verification_evidence_ids: tuple[str, ...]
    title: str
    body: str
    credential_ref: str
    consequence_preview: tuple[str, ...]
    remote_observation_id: str
    created_at: datetime
    expires_at: datetime
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in (
            "proposal_id", "task_id", "repository_root", "remote_name",
            "source_ref", "target_ref", "title", "body", "credential_ref",
            "remote_observation_id",
        ):
            text(getattr(self, name), name)
        digest(self.remote_url_sha256, "remote_url_sha256", required=True)
        digest(self.complete_diff_sha256, "complete_diff_sha256", required=True)
        if self.expected_old_object_id is not None:
            _object_id(self.expected_old_object_id, "expected_old_object_id")
        _object_id(self.proposed_new_object_id, "proposed_new_object_id")
        _ref(self.source_ref)
        _ref(self.target_ref)
        _secret_ref(self.credential_ref)
        _object_ids(self.commit_object_ids)
        texts(self.verification_evidence_ids, "verification_evidence_ids")
        texts(self.consequence_preview, "consequence_preview")
        aware(self.created_at, "created_at")
        aware(self.expires_at, "expires_at")
        if self.expires_at <= self.created_at:
            raise ValueError("Git publication proposal expiry is invalid")
        _validate_grant(self)
        _version(self.contract_version)

    def approval(self, approved_at: datetime) -> GitPublicationApproval:
        aware(approved_at, "approved_at")
        if not self.created_at <= approved_at < self.expires_at:
            raise PermissionError("Git publication proposal expired before approval")
        return GitPublicationApproval(
            f"approval-{self.proposal_id}", self.task_id, self.grant.grant_id,
            self.kind, self.repository_root, self.remote_name,
            self.remote_url_sha256, self.source_ref, self.target_ref,
            self.expected_old_object_id, self.proposed_new_object_id,
            self.commit_object_ids, self.complete_diff_sha256,
            self.verification_evidence_ids, self.title, self.body,
            self.credential_ref, self.consequence_preview, approved_at,
            self.expires_at,
        )


def git_publication_proposal_digest(proposal: GitPublicationProposal) -> str:
    """Bind the complete displayed proposal, including its separate grant."""
    payload = json.dumps(
        asdict(proposal), sort_keys=True, separators=(",", ":"),
        default=_json_value, allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _validate_grant(proposal: GitPublicationProposal) -> None:
    grant, scope = proposal.grant, proposal.grant.scope
    if (
        grant.owner_id != grant.principal_id
        or EngineeringAuthority.PUBLISH not in grant.authorities
        or EngineeringAuthority.SECRET_USE not in grant.authorities
        or scope.kind is not EngineeringGrantScopeKind.TASK
        or scope.scope_id != proposal.task_id
        or scope.workspace_roots != (proposal.repository_root,)
        or scope.git_remotes != (proposal.remote_name,)
        or scope.git_branches != (proposal.target_ref,)
        or scope.secret_refs != (proposal.credential_ref,)
        or grant.secret_exposure
        is not SecretExposurePolicy.OPAQUE_CREDENTIAL_INJECTION
    ):
        raise ValueError("Git publication proposal grant is not exact")


def _object_ids(values: tuple[str, ...]) -> None:
    if not values:
        raise ValueError("Git publication proposal requires commit object IDs")
    for value in values:
        _object_id(value, "commit object ID")


def _ref(value: str) -> None:
    if not _REF.fullmatch(value) or ".." in value or "//" in value:
        raise ValueError("Git publication ref is unsafe")


def _secret_ref(value: str) -> None:
    if not _SECRET_REF.fullmatch(value):
        raise ValueError("Git publication credential reference must be an opaque secret.* name")


def _object_id(value: str, name: str) -> None:
    if len(value) not in {40, 64}:
        raise ValueError(f"{name} must be a Git SHA-1 or SHA-256 object ID")
    try:
        int(value, 16)
    except ValueError as error:
        raise ValueError(f"{name} must be hexadecimal") from error


def _json_value(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    raise TypeError(f"unsupported publication digest value: {type(value)!r}")


def _version(value: str) -> None:
    if value != ENGINEERING_CONTRACT_VERSION:
        raise ValueError("Git publication proposal version is unsupported")
