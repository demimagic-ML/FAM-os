"""Signed recipe, raw-shell, sandbox, and polyglot qualification contracts."""

import base64
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from fam_os.core.engineering._validation import aware, digest, positive, relative_path, text, texts
from fam_os.core.engineering.authority import EngineeringAuthority
from fam_os.core.engineering.version import ENGINEERING_CONTRACT_VERSION


class EngineeringEcosystem(StrEnum):
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    RUST = "rust"
    GO = "go"
    JAVA = "java"
    KOTLIN = "kotlin"
    C = "c"
    CPP = "cpp"
    SHELL = "shell"
    HTML = "html"
    CSS = "css"


class ToolRecipePurpose(StrEnum):
    BUILD = "build"
    TEST = "test"
    LINT = "lint"
    FORMAT_CHECK = "format_check"
    TYPE_CHECK = "type_check"
    STATIC_ANALYSIS = "static_analysis"
    COVERAGE = "coverage"
    PACKAGE = "package"
    LANGUAGE_DIAGNOSTICS = "language_diagnostics"
    ACCEPTANCE = "acceptance"
    STACK_TRACE = "stack_trace"
    CRASH_DUMP = "crash_dump"
    TRACE = "trace"
    CPU_PROFILE = "cpu_profile"
    MEMORY_PROFILE = "memory_profile"
    RACE_DETECTION = "race_detection"
    LEAK_DETECTION = "leak_detection"
    PERFORMANCE_REGRESSION = "performance_regression"


class SandboxNetworkMode(StrEnum):
    DENIED = "denied"
    ALLOWLIST_PROXY = "allowlist_proxy"


class ToolQualificationStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"


class RawShellPrivilegeTier(StrEnum):
    UNPRIVILEGED_CANDIDATE = "unprivileged_candidate"
    HOST_USER = "host_user"
    HOST_ADMIN = "host_admin"


class ToolchainMountSourceKind(StrEnum):
    HOST_ABSOLUTE = "host_absolute"
    INSTALLED_RELEASE = "installed_release"


@dataclass(frozen=True, slots=True)
class ToolchainMount:
    source_path: str
    sandbox_path: str
    tree_sha256: str
    source_kind: ToolchainMountSourceKind = ToolchainMountSourceKind.HOST_ABSOLUTE

    def __post_init__(self) -> None:
        if self.source_kind is ToolchainMountSourceKind.HOST_ABSOLUTE:
            if not self.source_path.startswith("/"):
                raise ValueError("host toolchain source path must be absolute")
            if self.source_path in {"/home", "/root"} or len(self.source_path.split("/")) < 4:
                raise ValueError("toolchain mount cannot expose a host home or broad root")
        else:
            relative_path(self.source_path, "installed release toolchain source path")
            if not self.source_path.startswith("share/expert/toolchains/"):
                raise ValueError("installed toolchains must be release-owned expert assets")
        if not self.sandbox_path.startswith("/opt/fam/toolchains/"):
            raise ValueError("toolchains must mount below /opt/fam/toolchains")
        digest(self.tree_sha256, "tree_sha256", required=True)


@dataclass(frozen=True, slots=True)
class SignedToolRecipe:
    recipe_id: str
    recipe_version: str
    ecosystem: EngineeringEcosystem
    purpose: ToolRecipePurpose
    executable_path: str
    argv_template: tuple[str, ...]
    allowed_environment_keys: tuple[str, ...]
    expected_exit_codes: tuple[int, ...]
    verifier_ids: tuple[str, ...]
    signer_key_id: str
    payload_sha256: str
    signature_base64: str
    toolchain_mounts: tuple[ToolchainMount, ...] = ()
    network_mode: SandboxNetworkMode = SandboxNetworkMode.DENIED
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in ("recipe_id", "recipe_version", "executable_path", "signer_key_id", "signature_base64"):
            text(getattr(self, name), name)
        if not self.executable_path.startswith("/"):
            raise ValueError("signed recipe executable must be absolute")
        texts(self.argv_template, "argv_template", unique=False)
        texts(self.allowed_environment_keys, "allowed_environment_keys")
        if any(key in _FORBIDDEN_ENVIRONMENT for key in self.allowed_environment_keys):
            raise ValueError("signed recipe cannot inherit credentials or host home")
        if not self.expected_exit_codes or len(set(self.expected_exit_codes)) != len(self.expected_exit_codes):
            raise ValueError("signed recipe expected exit codes must be unique and nonempty")
        if any(isinstance(code, bool) or not isinstance(code, int) for code in self.expected_exit_codes):
            raise ValueError("signed recipe exit codes must be integers")
        texts(self.verifier_ids, "verifier_ids")
        digest(self.payload_sha256, "payload_sha256", required=True)
        try:
            signature = base64.b64decode(self.signature_base64, validate=True)
        except (ValueError, TypeError) as error:
            raise ValueError("tool recipe signature must be strict base64") from error
        if len(signature) != 64:
            raise ValueError("tool recipe Ed25519 signature must be 64 bytes")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("signed tool recipe contract version is unsupported")


@dataclass(frozen=True, slots=True)
class EngineeringSandboxProfile:
    profile_id: str
    memory_bytes: int
    cpu_seconds: int
    wall_seconds: int
    process_limit: int
    output_bytes: int
    artifact_bytes: int
    network_mode: SandboxNetworkMode
    network_hosts: tuple[str, ...]
    sanitized_environment: tuple[tuple[str, str], ...]
    host_home_mounted: bool = False
    inherited_credentials: bool = False
    git_hooks_enabled: bool = False

    def __post_init__(self) -> None:
        text(self.profile_id, "profile_id")
        for name in ("memory_bytes", "cpu_seconds", "wall_seconds", "process_limit", "output_bytes", "artifact_bytes"):
            positive(getattr(self, name), name)
        texts(self.network_hosts, "network_hosts")
        keys = tuple(key for key, _value in self.sanitized_environment)
        texts(keys, "sanitized environment keys")
        if any(key in _FORBIDDEN_ENVIRONMENT for key in keys):
            raise ValueError("sandbox environment cannot contain host secrets or home")
        if self.network_mode is SandboxNetworkMode.DENIED and self.network_hosts:
            raise ValueError("network-denied profile cannot name destinations")
        if self.network_mode is SandboxNetworkMode.ALLOWLIST_PROXY and not self.network_hosts:
            raise ValueError("network proxy profile requires exact destinations")
        if self.host_home_mounted or self.inherited_credentials or self.git_hooks_enabled:
            raise ValueError("engineering sandbox cannot expose home, credentials, or Git hooks")


@dataclass(frozen=True, slots=True)
class RawShellAuthorization:
    authorization_id: str
    grant_id: str
    task_id: str
    principal_id: str
    workspace_root: str
    shell_executable: str
    command_sha256: str
    environment: tuple[tuple[str, str], ...]
    privilege_tier: RawShellPrivilegeTier
    issued_at: datetime
    expires_at: datetime
    single_use: bool = True
    required_authority: EngineeringAuthority = EngineeringAuthority.RAW_SHELL
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in ("authorization_id", "grant_id", "task_id", "principal_id", "workspace_root", "shell_executable"):
            text(getattr(self, name), name)
        if not self.workspace_root.startswith("/") or not self.shell_executable.startswith("/"):
            raise ValueError("raw shell workspace and executable must be absolute")
        digest(self.command_sha256, "command_sha256", required=True)
        aware(self.issued_at, "issued_at")
        aware(self.expires_at, "expires_at")
        if self.expires_at <= self.issued_at or not self.single_use:
            raise ValueError("raw shell authorization must be expiring and single-use")
        keys = tuple(key for key, _value in self.environment)
        texts(keys, "raw shell environment keys")
        if self.required_authority is not EngineeringAuthority.RAW_SHELL:
            raise ValueError("raw shell requires its distinct authority")
        if self.privilege_tier is RawShellPrivilegeTier.HOST_ADMIN:
            raise ValueError("host administration must use the separate broker")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("raw shell authorization contract version is unsupported")


@dataclass(frozen=True, slots=True)
class EngineeringToolReceipt:
    receipt_id: str
    task_id: str
    candidate_id: str
    recipe_id: str
    recipe_payload_sha256: str
    sandbox_profile_id: str
    command_sha256: str
    started_at: datetime
    completed_at: datetime
    exit_code: int | None
    stdout_sha256: str
    stderr_sha256: str
    artifact_digests: tuple[str, ...]
    network_destinations: tuple[str, ...]
    isolation_evidence_ids: tuple[str, ...]
    status: ToolQualificationStatus
    diagnostic: str = ""
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in ("receipt_id", "task_id", "candidate_id", "recipe_id", "sandbox_profile_id"):
            text(getattr(self, name), name)
        for name in ("recipe_payload_sha256", "command_sha256", "stdout_sha256", "stderr_sha256"):
            digest(getattr(self, name), name, required=True)
        for value in self.artifact_digests:
            digest(value, "artifact digest", required=True)
        texts(self.network_destinations, "network_destinations")
        texts(self.isolation_evidence_ids, "isolation_evidence_ids")
        aware(self.started_at, "started_at")
        aware(self.completed_at, "completed_at")
        if self.completed_at < self.started_at:
            raise ValueError("tool receipt completion cannot predate start")
        if self.status in {ToolQualificationStatus.PASSED, ToolQualificationStatus.FAILED} and self.exit_code is None:
            raise ValueError("completed tool receipt requires an exit code")
        if len(self.diagnostic.encode("utf-8")) > 4_096:
            raise ValueError("tool receipt diagnostic exceeds its bound")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("tool receipt contract version is unsupported")


@dataclass(frozen=True, slots=True)
class LanguageToolQualification:
    qualification_id: str
    ecosystem: EngineeringEcosystem
    tool_name: str
    tool_version: str | None
    positive_receipt_id: str | None
    negative_receipt_id: str | None
    status: ToolQualificationStatus
    qualified_at: datetime
    installed_release_id: str | None = None
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        text(self.qualification_id, "qualification_id")
        text(self.tool_name, "tool_name")
        aware(self.qualified_at, "qualified_at")
        for name in ("tool_version", "positive_receipt_id", "negative_receipt_id", "installed_release_id"):
            value = getattr(self, name)
            if value is not None:
                text(value, name)
        if self.status is ToolQualificationStatus.PASSED and (self.positive_receipt_id is None or self.negative_receipt_id is None):
            raise ValueError("passed language qualification requires positive and negative receipts")
        if self.status is ToolQualificationStatus.UNAVAILABLE and self.tool_version is not None:
            raise ValueError("unavailable tool cannot claim a version")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("language qualification contract version is unsupported")


_FORBIDDEN_ENVIRONMENT = frozenset({
    "HOME", "SSH_AUTH_SOCK", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY",
    "GITHUB_TOKEN", "GIT_ASKPASS", "NPM_TOKEN", "PIP_INDEX_URL",
})
