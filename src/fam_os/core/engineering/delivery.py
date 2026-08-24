"""Design-asset and Git delivery proposal contracts."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from fam_os.core.engineering._validation import (
    absolute_path,
    aware,
    digest,
    relative_path,
    text,
    texts,
    unique_enum,
)
from fam_os.core.engineering.authority import EngineeringAuthority
from fam_os.core.engineering.version import ENGINEERING_CONTRACT_VERSION


class GitOperationKind(StrEnum):
    CREATE_BRANCH = "create_branch"
    COMMIT = "commit"
    MERGE = "merge"
    REBASE = "rebase"
    TAG = "tag"
    PUSH = "push"
    OPEN_CHANGE_REQUEST = "open_change_request"


@dataclass(frozen=True, slots=True)
class DesignAsset:
    path: str
    media_type: str
    content_sha256: str
    source_asset_id: str | None
    width: int | None
    height: int | None

    def __post_init__(self) -> None:
        relative_path(self.path, "path")
        text(self.media_type, "media_type")
        digest(self.content_sha256, "content_sha256", required=True)
        if self.source_asset_id is not None:
            text(self.source_asset_id, "source_asset_id")
        if (self.width is None) != (self.height is None):
            raise ValueError("design dimensions must be supplied together")
        for name in ("width", "height"):
            value = getattr(self, name)
            if value is not None and (isinstance(value, bool) or value <= 0):
                raise ValueError(f"{name} must be positive when present")


@dataclass(frozen=True, slots=True)
class DesignAssetManifest:
    manifest_id: str
    task_id: str
    created_at: datetime
    design_system_id: str | None
    assets: tuple[DesignAsset, ...]
    required_verifier_ids: tuple[str, ...]
    accessibility_review_required: bool
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        text(self.manifest_id, "manifest_id")
        text(self.task_id, "task_id")
        aware(self.created_at, "created_at")
        if self.design_system_id is not None:
            text(self.design_system_id, "design_system_id")
        if not self.assets:
            raise ValueError("design asset manifest must contain assets")
        paths = tuple(asset.path for asset in self.assets)
        texts(paths, "design asset paths")
        texts(self.required_verifier_ids, "required_verifier_ids")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("design asset manifest contract version is unsupported")


@dataclass(frozen=True, slots=True)
class GitOperation:
    operation_id: str
    task_id: str
    kind: GitOperationKind
    repository_root: str
    remote: str | None
    source_ref: str | None
    target_ref: str
    commit_sha256: str | None
    message: str
    required_authorities: tuple[EngineeringAuthority, ...]
    force: bool
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in ("operation_id", "task_id", "target_ref", "message"):
            text(getattr(self, name), name)
        absolute_path(self.repository_root, "repository_root")
        for name in ("remote", "source_ref"):
            value = getattr(self, name)
            if value is not None:
                text(value, name)
        digest(self.commit_sha256, "commit_sha256")
        unique_enum(self.required_authorities, "required_authorities")
        if EngineeringAuthority.MODIFY not in self.required_authorities:
            raise ValueError("git operation requires modify authority")
        if self.kind in {GitOperationKind.PUSH, GitOperationKind.OPEN_CHANGE_REQUEST}:
            if self.remote is None or EngineeringAuthority.PUBLISH not in self.required_authorities:
                raise ValueError("remote Git delivery requires a remote and publish authority")
        if self.force and EngineeringAuthority.PROTECTED_REF_WRITE not in self.required_authorities:
            raise ValueError("forced Git operation requires protected-ref authority")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("git operation contract version is unsupported")
