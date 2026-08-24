"""Deterministic tool execution and dependency-change contracts."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from fam_os.core.engineering._validation import (
    absolute_path,
    aware,
    digest,
    positive,
    relative_path,
    text,
    texts,
    unique_enum,
)
from fam_os.core.engineering.authority import EngineeringAuthority
from fam_os.core.engineering.version import ENGINEERING_CONTRACT_VERSION


class ToolRunStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    DENIED = "denied"


class DependencyAction(StrEnum):
    ADD = "add"
    UPDATE = "update"
    REMOVE = "remove"


@dataclass(frozen=True, slots=True)
class ToolRecipe:
    recipe_id: str
    task_id: str
    argv: tuple[str, ...]
    working_directory: str
    environment_keys: tuple[str, ...]
    timeout_seconds: int
    network_required: bool
    required_authorities: tuple[EngineeringAuthority, ...]
    expected_exit_codes: tuple[int, ...]
    verifier_ids: tuple[str, ...]
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        text(self.recipe_id, "recipe_id")
        text(self.task_id, "task_id")
        if not self.argv:
            raise ValueError("argv must not be empty")
        texts(self.argv, "argv", unique=False)
        absolute_path(self.working_directory, "working_directory")
        texts(self.environment_keys, "environment_keys")
        positive(self.timeout_seconds, "timeout_seconds")
        unique_enum(self.required_authorities, "required_authorities")
        if EngineeringAuthority.EXECUTE not in self.required_authorities:
            raise ValueError("tool recipe requires execute authority")
        if self.network_required and EngineeringAuthority.NETWORK not in self.required_authorities:
            raise ValueError("networked tool recipe requires network authority")
        if not self.expected_exit_codes or any(
            isinstance(code, bool) or not isinstance(code, int) for code in self.expected_exit_codes
        ):
            raise ValueError("expected_exit_codes must contain integers")
        if len(set(self.expected_exit_codes)) != len(self.expected_exit_codes):
            raise ValueError("expected_exit_codes must not contain duplicates")
        texts(self.verifier_ids, "verifier_ids")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("tool recipe contract version is unsupported")


@dataclass(frozen=True, slots=True)
class ToolRun:
    run_id: str
    task_id: str
    recipe_id: str
    started_at: datetime
    completed_at: datetime
    status: ToolRunStatus
    exit_code: int | None
    stdout_sha256: str
    stderr_sha256: str
    evidence_ids: tuple[str, ...]
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in ("run_id", "task_id", "recipe_id"):
            text(getattr(self, name), name)
        aware(self.started_at, "started_at")
        aware(self.completed_at, "completed_at")
        if self.completed_at < self.started_at:
            raise ValueError("completed_at cannot precede started_at")
        if self.exit_code is not None and (
            isinstance(self.exit_code, bool) or not isinstance(self.exit_code, int)
        ):
            raise ValueError("exit_code must be an integer when present")
        if self.status in {ToolRunStatus.SUCCEEDED, ToolRunStatus.FAILED} and self.exit_code is None:
            raise ValueError("completed tool run requires an exit code")
        digest(self.stdout_sha256, "stdout_sha256", required=True)
        digest(self.stderr_sha256, "stderr_sha256", required=True)
        texts(self.evidence_ids, "evidence_ids")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("tool run contract version is unsupported")


@dataclass(frozen=True, slots=True)
class DependencyChange:
    ecosystem: str
    package: str
    action: DependencyAction
    current_version: str | None
    requested_version: str | None
    registry: str | None

    def __post_init__(self) -> None:
        text(self.ecosystem, "ecosystem")
        text(self.package, "package")
        for name in ("current_version", "requested_version", "registry"):
            value = getattr(self, name)
            if value is not None:
                text(value, name)
        if self.action is DependencyAction.REMOVE and self.requested_version is not None:
            raise ValueError("removed dependency cannot have a requested version")
        if self.action is not DependencyAction.REMOVE and self.requested_version is None:
            raise ValueError("added or updated dependency requires a version")


@dataclass(frozen=True, slots=True)
class DependencyPlan:
    plan_id: str
    task_id: str
    lockfile_path: str
    changes: tuple[DependencyChange, ...]
    required_authorities: tuple[EngineeringAuthority, ...]
    vulnerability_scan_required: bool
    license_check_required: bool
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        text(self.plan_id, "plan_id")
        text(self.task_id, "task_id")
        relative_path(self.lockfile_path, "lockfile_path")
        if not self.changes:
            raise ValueError("dependency plan must contain changes")
        identities = tuple((change.ecosystem, change.package) for change in self.changes)
        if len(set(identities)) != len(identities):
            raise ValueError("dependency plan must not repeat a package")
        unique_enum(self.required_authorities, "required_authorities")
        if EngineeringAuthority.MODIFY not in self.required_authorities:
            raise ValueError("dependency plan requires modify authority")
        if any(change.registry is not None for change in self.changes):
            if EngineeringAuthority.NETWORK not in self.required_authorities:
                raise ValueError("registry dependency plan requires network authority")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("dependency plan contract version is unsupported")
