"""Target-bound, expiring, revocable owner engineering grants."""

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
from fam_os.core.engineering.authority import EngineeringAuthority
from fam_os.core.engineering.delegation import EngineeringDelegationMode, expand_delegation
from fam_os.core.engineering.version import ENGINEERING_CONTRACT_VERSION


class EngineeringGrantScopeKind(StrEnum):
    ACTION = "action"
    CHANGESET = "changeset"
    TASK = "task"
    SESSION = "session"


class GrantLifecycleState(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"
    CONSUMED = "consumed"


class VerificationRequirement(StrEnum):
    REQUIRED = "required"
    ALLOW_UNVERIFIED = "allow_unverified"
    WAIVED = "waived"


class SecretExposurePolicy(StrEnum):
    NONE = "none"
    NAMED_REFERENCES = "named_references"
    PLAINTEXT_TO_APPROVED_TOOL = "plaintext_to_approved_tool"
    OPAQUE_CREDENTIAL_INJECTION = "opaque_credential_injection"
    REDACTED_TRANSFORMATION = "redacted_transformation"
    DIRECT_MODEL_VISIBLE_DISCLOSURE = "direct_model_visible_disclosure"


class ReversibilityPolicy(StrEnum):
    REQUIRED = "required"
    BEST_EFFORT = "best_effort"
    NOT_REQUIRED = "not_required"


BREAK_GLASS_AUTHORITIES = frozenset({
    EngineeringAuthority.RAW_SHELL,
    EngineeringAuthority.HOST_ADMIN,
    EngineeringAuthority.GLOBAL_INSTALL,
    EngineeringAuthority.PRODUCTION_MUTATE,
    EngineeringAuthority.POLICY_CHANGE,
    EngineeringAuthority.PROTECTED_REF_WRITE,
    EngineeringAuthority.SELF_UPDATE,
})


@dataclass(frozen=True, slots=True)
class EngineeringResourceImpact:
    max_wall_seconds: int
    max_tool_runs: int
    max_processes: int
    max_changed_files: int
    max_changed_bytes: int
    max_network_bytes: int

    def __post_init__(self) -> None:
        for name in (
            "max_wall_seconds", "max_tool_runs", "max_processes",
            "max_changed_files", "max_changed_bytes", "max_network_bytes",
        ):
            positive(getattr(self, name), name, allow_zero=True)


@dataclass(frozen=True, slots=True)
class EngineeringGrantScope:
    kind: EngineeringGrantScopeKind
    scope_id: str
    workspace_roots: tuple[str, ...]
    path_allowlist: tuple[str, ...]
    path_denylist: tuple[str, ...]
    toolchains: tuple[str, ...]
    network_hosts: tuple[str, ...]
    package_registries: tuple[str, ...]
    git_remotes: tuple[str, ...]
    git_branches: tuple[str, ...]
    secret_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        text(self.scope_id, "scope_id")
        if not self.workspace_roots:
            raise ValueError("grant scope requires a workspace root")
        for root in self.workspace_roots:
            absolute_path(root, "workspace_roots item")
        for name in (
            "workspace_roots", "path_allowlist", "path_denylist", "toolchains",
            "network_hosts", "package_registries", "git_remotes", "git_branches",
            "secret_refs",
        ):
            texts(getattr(self, name), name)


@dataclass(frozen=True, slots=True)
class EngineeringAuthorityGrant:
    grant_id: str
    owner_id: str
    principal_id: str
    mode: EngineeringDelegationMode
    authorities: tuple[EngineeringAuthority, ...]
    scope: EngineeringGrantScope
    purpose: str
    issued_at: datetime
    expires_at: datetime
    state: GrantLifecycleState
    reversibility: ReversibilityPolicy
    secret_exposure: SecretExposurePolicy
    verification: VerificationRequirement
    resource_impact: EngineeringResourceImpact
    inheritable: bool = False
    break_glass_decision_id: str | None = None
    revoked_at: datetime | None = None
    consumed_at: datetime | None = None
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in ("grant_id", "owner_id", "principal_id", "purpose"):
            text(getattr(self, name), name)
        aware(self.issued_at, "issued_at")
        aware(self.expires_at, "expires_at")
        if self.expires_at <= self.issued_at:
            raise ValueError("grant expiry must follow issue time")
        unique_enum(self.authorities, "authorities")
        expected = expand_delegation(
            self.mode,
            self.authorities if self.mode is EngineeringDelegationMode.CUSTOM else (),
        )
        if self.authorities != expected:
            raise ValueError("grant authorities must equal visible delegation expansion")
        if self.inheritable and self._high_risk:
            raise ValueError("high-risk grants cannot be inheritable")
        self._validate_scope_authority()
        self._validate_lifecycle()
        if self._requires_break_glass and self.break_glass_decision_id is None:
            raise ValueError("high-risk or waived grant requires break-glass decision")
        if not self._requires_break_glass and self.break_glass_decision_id is not None:
            raise ValueError("ordinary grant must not carry break-glass authority")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("engineering grant contract version is unsupported")

    @property
    def _high_risk(self) -> bool:
        return bool(set(self.authorities) & BREAK_GLASS_AUTHORITIES)

    @property
    def _requires_break_glass(self) -> bool:
        return (
            self._high_risk
            or self.verification is VerificationRequirement.WAIVED
            or self.secret_exposure
            is SecretExposurePolicy.DIRECT_MODEL_VISIBLE_DISCLOSURE
        )

    @property
    def requires_break_glass(self) -> bool:
        return self._requires_break_glass

    def active_at(self, instant: datetime) -> bool:
        aware(instant, "instant")
        return (
            self.state is GrantLifecycleState.ACTIVE
            and self.issued_at <= instant < self.expires_at
        )

    def _validate_scope_authority(self) -> None:
        granted = set(self.authorities)
        if (self.scope.network_hosts or self.scope.package_registries):
            if EngineeringAuthority.NETWORK not in granted:
                raise ValueError("network scope requires network authority")
        if self.scope.secret_refs and EngineeringAuthority.SECRET_USE not in granted:
            raise ValueError("secret scope requires secret-use authority")
        if self.secret_exposure is not SecretExposurePolicy.NONE:
            if EngineeringAuthority.SECRET_USE not in granted or not self.scope.secret_refs:
                raise ValueError("secret exposure requires authority and named secret scope")
        if self.scope.git_remotes and EngineeringAuthority.PUBLISH not in granted:
            raise ValueError("Git remote scope requires publish authority")

    def _validate_lifecycle(self) -> None:
        for name in ("revoked_at", "consumed_at"):
            value = getattr(self, name)
            if value is not None:
                aware(value, name)
                if value < self.issued_at:
                    raise ValueError(f"{name} cannot predate grant issue")
        expected = {
            GrantLifecycleState.ACTIVE: (False, False),
            GrantLifecycleState.REVOKED: (True, False),
            GrantLifecycleState.CONSUMED: (False, True),
        }[self.state]
        if expected != (self.revoked_at is not None, self.consumed_at is not None):
            raise ValueError("grant lifecycle state and timestamps disagree")


@dataclass(frozen=True, slots=True)
class OwnerGrantApproval:
    approval_id: str
    grant_id: str
    owner_id: str
    grant_sha256: str
    approved_at: datetime
    authentication_context_id: str
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        from fam_os.core.engineering._validation import digest

        for name in (
            "approval_id", "grant_id", "owner_id", "authentication_context_id",
        ):
            text(getattr(self, name), name)
        digest(self.grant_sha256, "grant_sha256", required=True)
        aware(self.approved_at, "approved_at")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("owner grant approval version is unsupported")


@dataclass(frozen=True, slots=True)
class EngineeringAuthorizationRequest:
    request_id: str
    grant_id: str
    principal_id: str
    authority: EngineeringAuthority
    task_id: str
    session_id: str
    action_id: str | None
    change_set_id: str | None
    workspace_root: str
    path: str | None
    toolchain: str | None
    network_host: str | None
    package_registry: str | None
    git_remote: str | None
    git_branch: str | None
    secret_ref: str | None
    resource_impact: EngineeringResourceImpact
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        from fam_os.core.engineering._validation import relative_path

        for name in ("request_id", "grant_id", "principal_id", "task_id", "session_id"):
            text(getattr(self, name), name)
        absolute_path(self.workspace_root, "workspace_root")
        if self.path is not None:
            relative_path(self.path, "path")
        for name in (
            "action_id", "change_set_id", "toolchain", "network_host",
            "package_registry", "git_remote", "git_branch", "secret_ref",
        ):
            value = getattr(self, name)
            if value is not None:
                text(value, name)
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("engineering authorization request version is unsupported")


@dataclass(frozen=True, slots=True)
class EngineeringAuthorizationDecision:
    decision_id: str
    request_id: str
    grant_id: str
    authority: EngineeringAuthority
    decided_at: datetime
    allowed: bool
    reason_code: str
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in ("decision_id", "request_id", "grant_id", "reason_code"):
            text(getattr(self, name), name)
        aware(self.decided_at, "decided_at")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("engineering authorization decision version is unsupported")
