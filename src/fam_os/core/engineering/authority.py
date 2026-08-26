"""Owner-delegated engineering authority and bounded task admission."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from fam_os.core.engineering._validation import (
    absolute_path,
    aware,
    positive,
    text,
    texts,
    unique_enum,
)
from fam_os.core.engineering.version import ENGINEERING_CONTRACT_VERSION


class EngineeringAuthority(StrEnum):
    OBSERVE = "observe"
    PROPOSE = "propose"
    MODIFY = "modify"
    EXECUTE = "execute"
    APPLICATION_TEST = "application_test"
    NETWORK = "network"
    PUBLISH = "publish"
    RAW_SHELL = "raw_shell"
    HOST_ADMIN = "host_admin"
    SECRET_USE = "secret_use"
    GLOBAL_INSTALL = "global_install"
    PRODUCTION_MUTATE = "production_mutate"
    POLICY_CHANGE = "policy_change"
    PROTECTED_REF_WRITE = "protected_ref_write"
    SELF_UPDATE = "self_update"


class EngineeringOperation(StrEnum):
    READ = "read"
    CREATE = "create"
    REPLACE = "replace"
    DELETE = "delete"
    MOVE = "move"
    RUN_TOOL = "run_tool"
    MANAGE_DEPENDENCY = "manage_dependency"
    MANAGE_DESIGN = "manage_design"
    GIT_WRITE = "git_write"
    PUBLISH = "publish"


class CheckpointPolicy(StrEnum):
    NONE = "none"
    BEFORE_EFFECTS = "before_effects"
    BEFORE_IRREVERSIBLE_EFFECTS = "before_irreversible_effects"
    EVERY_CHANGESET = "every_changeset"


@dataclass(frozen=True, slots=True)
class EngineeringTaskEnvelope:
    task_id: str
    owner_id: str
    grant_id: str
    intent: str
    created_at: datetime
    expires_at: datetime
    workspace_roots: tuple[str, ...]
    authorities: tuple[EngineeringAuthority, ...]
    permitted_operations: tuple[EngineeringOperation, ...]
    path_allowlist: tuple[str, ...]
    path_denylist: tuple[str, ...]
    toolchains: tuple[str, ...]
    network_hosts: tuple[str, ...]
    package_registries: tuple[str, ...]
    max_wall_seconds: int
    max_tool_runs: int
    max_changed_files: int
    max_changed_bytes: int
    git_remote: str | None
    git_branch: str | None
    checkpoint_policy: CheckpointPolicy
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in ("task_id", "owner_id", "grant_id", "intent"):
            text(getattr(self, name), name)
        aware(self.created_at, "created_at")
        aware(self.expires_at, "expires_at")
        if self.expires_at <= self.created_at:
            raise ValueError("expires_at must be later than created_at")
        if not self.workspace_roots:
            raise ValueError("workspace_roots must not be empty")
        for root in self.workspace_roots:
            absolute_path(root, "workspace_roots item")
        texts(self.workspace_roots, "workspace_roots")
        unique_enum(self.authorities, "authorities")
        unique_enum(self.permitted_operations, "permitted_operations")
        texts(self.path_allowlist, "path_allowlist")
        texts(self.path_denylist, "path_denylist")
        texts(self.toolchains, "toolchains")
        texts(self.network_hosts, "network_hosts")
        texts(self.package_registries, "package_registries")
        for name in (
            "max_wall_seconds", "max_tool_runs", "max_changed_files",
            "max_changed_bytes",
        ):
            positive(getattr(self, name), name, allow_zero=True)
        self._validate_authority_dependencies()
        self._validate_git_binding()
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("engineering task contract version is unsupported")

    def _validate_authority_dependencies(self) -> None:
        granted = set(self.authorities)
        operations = set(self.permitted_operations)
        modifying = operations - {EngineeringOperation.READ, EngineeringOperation.RUN_TOOL}
        if modifying and EngineeringAuthority.MODIFY not in granted:
            raise ValueError("modifying operations require modify authority")
        if EngineeringOperation.RUN_TOOL in operations and EngineeringAuthority.EXECUTE not in granted:
            raise ValueError("run_tool requires execute authority")
        if self.network_hosts and EngineeringAuthority.NETWORK not in granted:
            raise ValueError("network hosts require network authority")
        if self.package_registries and EngineeringAuthority.NETWORK not in granted:
            raise ValueError("package registries require network authority")
        if EngineeringOperation.PUBLISH in operations and EngineeringAuthority.PUBLISH not in granted:
            raise ValueError("publish operation requires publish authority")

    def _validate_git_binding(self) -> None:
        if (self.git_remote is None) != (self.git_branch is None):
            raise ValueError("git_remote and git_branch must be supplied together")
        for name in ("git_remote", "git_branch"):
            value = getattr(self, name)
            if value is not None:
                text(value, name)
