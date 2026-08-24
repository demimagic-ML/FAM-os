"""Bounded runtime-diagnostics requests, artifacts, and evidence receipts."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from fam_os.core.engineering._validation import aware, digest, positive, text, texts
from fam_os.core.engineering.authority import EngineeringAuthority
from fam_os.core.engineering.execution import SandboxNetworkMode
from fam_os.core.engineering.version import ENGINEERING_CONTRACT_VERSION


class RuntimeDiagnosticKind(StrEnum):
    STACK_TRACE = "stack_trace"
    CRASH_DUMP = "crash_dump"
    TRACE = "trace"
    CPU_PROFILE = "cpu_profile"
    MEMORY_PROFILE = "memory_profile"
    RACE_DETECTION = "race_detection"
    LEAK_DETECTION = "leak_detection"
    PERFORMANCE_REGRESSION = "performance_regression"


class DiagnosticArtifactKind(StrEnum):
    STACK_TRACE = "stack_trace"
    CRASH_DUMP = "crash_dump"
    TRACE = "trace"
    PROFILE = "profile"
    RACE_REPORT = "race_report"
    LEAK_REPORT = "leak_report"
    PERFORMANCE_SAMPLE = "performance_sample"


class RuntimeDiagnosticStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    UNAVAILABLE = "unavailable"


class RuntimeDiagnosticPhase(StrEnum):
    BASELINE = "baseline"
    CANDIDATE = "candidate"
    POSTAPPLY = "postapply"


class RuntimePerformanceMode(StrEnum):
    NOT_APPLICABLE = "not_applicable"
    BASELINE_CAPTURE = "baseline_capture"
    COMPARISON = "comparison"


@dataclass(frozen=True, slots=True)
class RuntimeDiagnosticLimits:
    wall_seconds: int
    cpu_seconds: int
    memory_bytes: int
    process_limit: int
    output_bytes: int
    artifact_bytes: int
    sample_limit: int
    temporary_file_bytes: int
    unbounded_virtual_address_space: bool = False

    def __post_init__(self) -> None:
        for name in (
            "wall_seconds", "cpu_seconds", "memory_bytes", "process_limit",
            "output_bytes", "artifact_bytes", "sample_limit",
            "temporary_file_bytes",
        ):
            positive(getattr(self, name), name)
        if not isinstance(self.unbounded_virtual_address_space, bool):
            raise ValueError("virtual address-space policy must be boolean")


@dataclass(frozen=True, slots=True)
class RuntimeDiagnosticRequest:
    request_id: str
    task_id: str
    candidate_id: str
    grant_id: str
    principal_id: str
    session_id: str
    phase: RuntimeDiagnosticPhase
    signed_recipe_id: str
    signed_recipe_version: str
    recipe_payload_sha256: str
    kind: RuntimeDiagnosticKind
    target_argv: tuple[str, ...]
    allowed_environment_keys: tuple[str, ...]
    artifact_kinds: tuple[DiagnosticArtifactKind, ...]
    limits: RuntimeDiagnosticLimits
    network_mode: SandboxNetworkMode
    network_destinations: tuple[str, ...]
    created_at: datetime
    baseline_artifact_sha256: str | None = None
    baseline_value_microunits: int | None = None
    maximum_regression_ppm: int | None = None
    required_authority: EngineeringAuthority = EngineeringAuthority.EXECUTE
    performance_mode: RuntimePerformanceMode = RuntimePerformanceMode.NOT_APPLICABLE
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in (
            "request_id", "task_id", "candidate_id", "grant_id",
            "principal_id", "session_id", "signed_recipe_id",
            "signed_recipe_version",
        ):
            text(getattr(self, name), name)
        digest(self.recipe_payload_sha256, "recipe_payload_sha256", required=True)
        if not isinstance(self.phase, RuntimeDiagnosticPhase):
            raise ValueError("runtime diagnostic phase is invalid")
        texts(self.target_argv, "target_argv", unique=False)
        texts(self.allowed_environment_keys, "allowed_environment_keys")
        texts(self.network_destinations, "network_destinations")
        if not self.artifact_kinds or len(set(self.artifact_kinds)) != len(self.artifact_kinds):
            raise ValueError("runtime diagnostics require unique artifact kinds")
        forbidden = {"HOME", "SSH_AUTH_SOCK", "AWS_SECRET_ACCESS_KEY", "GITHUB_TOKEN"}
        if forbidden.intersection(self.allowed_environment_keys):
            raise ValueError("runtime diagnostics cannot inherit host credentials or home")
        if self.network_mode is SandboxNetworkMode.DENIED and self.network_destinations:
            raise ValueError("network-denied diagnostics cannot name destinations")
        if self.network_mode is SandboxNetworkMode.ALLOWLIST_PROXY and not self.network_destinations:
            raise ValueError("networked diagnostics require exact destinations")
        aware(self.created_at, "created_at")
        if self.required_authority is not EngineeringAuthority.EXECUTE:
            raise ValueError("runtime diagnostics require execute authority")
        if (
            self.limits.unbounded_virtual_address_space
            and self.kind not in {
                RuntimeDiagnosticKind.RACE_DETECTION,
                RuntimeDiagnosticKind.LEAK_DETECTION,
                RuntimeDiagnosticKind.CRASH_DUMP,
                RuntimeDiagnosticKind.STACK_TRACE,
            }
        ):
            raise ValueError("unbounded virtual address space is debugger-or-sanitizer-only")
        self._validate_baseline()
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("runtime diagnostic request contract version is unsupported")

    def _validate_baseline(self) -> None:
        if self.baseline_artifact_sha256 is not None:
            digest(self.baseline_artifact_sha256, "baseline_artifact_sha256", required=True)
        if self.kind is RuntimeDiagnosticKind.PERFORMANCE_REGRESSION:
            if self.performance_mode is RuntimePerformanceMode.NOT_APPLICABLE:
                raise ValueError("performance diagnostics require an explicit mode")
            positive(self.maximum_regression_ppm, "maximum_regression_ppm", allow_zero=True)
            if self.performance_mode is RuntimePerformanceMode.COMPARISON:
                if self.baseline_artifact_sha256 is None:
                    raise ValueError("performance diagnostics require an exact baseline artifact")
                positive(self.baseline_value_microunits, "baseline_value_microunits")
            elif (
                self.baseline_artifact_sha256 is not None
                or self.baseline_value_microunits is not None
            ):
                raise ValueError("baseline capture cannot cite a prior baseline")
        elif (
            self.performance_mode is not RuntimePerformanceMode.NOT_APPLICABLE
            or self.maximum_regression_ppm is not None
            or self.baseline_value_microunits is not None
        ):
            raise ValueError("baseline value and regression threshold are valid only for performance diagnostics")


@dataclass(frozen=True, slots=True)
class RuntimeDiagnosticArtifact:
    artifact_id: str
    kind: DiagnosticArtifactKind
    media_type: str
    sha256: str
    size_bytes: int
    sanitized: bool
    contains_secret_content: bool = False

    def __post_init__(self) -> None:
        text(self.artifact_id, "artifact_id")
        text(self.media_type, "media_type")
        digest(self.sha256, "sha256", required=True)
        positive(self.size_bytes, "size_bytes", allow_zero=True)
        if not self.sanitized or self.contains_secret_content:
            raise ValueError("diagnostic artifacts must be sanitized and secret-free")


@dataclass(frozen=True, slots=True)
class RuntimeDiagnosticReceipt:
    receipt_id: str
    request_id: str
    task_id: str
    candidate_id: str
    signed_recipe_id: str
    signed_recipe_version: str
    recipe_payload_sha256: str
    sandbox_profile_id: str
    started_at: datetime
    completed_at: datetime
    status: RuntimeDiagnosticStatus
    exit_code: int | None
    stdout_sha256: str
    stderr_sha256: str
    artifacts: tuple[RuntimeDiagnosticArtifact, ...]
    finding_ids: tuple[str, ...]
    isolation_evidence_ids: tuple[str, ...]
    authorization_decision_ids: tuple[str, ...]
    baseline_artifact_sha256: str | None = None
    observed_value_microunits: int | None = None
    regression_ppm: int | None = None
    diagnostic: str = ""
    performance_mode: RuntimePerformanceMode = RuntimePerformanceMode.NOT_APPLICABLE
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in (
            "receipt_id", "request_id", "task_id", "candidate_id",
            "signed_recipe_id", "signed_recipe_version", "sandbox_profile_id",
        ):
            text(getattr(self, name), name)
        for name in ("recipe_payload_sha256", "stdout_sha256", "stderr_sha256"):
            digest(getattr(self, name), name, required=True)
        aware(self.started_at, "started_at")
        aware(self.completed_at, "completed_at")
        if self.completed_at < self.started_at:
            raise ValueError("diagnostic receipt completion cannot predate start")
        texts(self.finding_ids, "finding_ids")
        texts(self.isolation_evidence_ids, "isolation_evidence_ids")
        texts(self.authorization_decision_ids, "authorization_decision_ids")
        if not self.authorization_decision_ids:
            raise ValueError("diagnostic receipt requires live execute authorization")
        if len({item.artifact_id for item in self.artifacts}) != len(self.artifacts):
            raise ValueError("diagnostic artifact identities must be unique")
        if self.status is RuntimeDiagnosticStatus.PASSED and self.exit_code != 0:
            raise ValueError("a passing diagnostic receipt requires exit code zero")
        self._validate_comparison()
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("runtime diagnostic receipt contract version is unsupported")

    def _validate_comparison(self) -> None:
        baseline = self.baseline_artifact_sha256
        measurements = self.observed_value_microunits, self.regression_ppm
        if self.performance_mode is RuntimePerformanceMode.BASELINE_CAPTURE:
            if (
                self.status is not RuntimeDiagnosticStatus.PASSED
                and baseline is None and all(value is None for value in measurements)
            ):
                return
            if baseline is None or any(value is None for value in measurements):
                raise ValueError("performance baseline capture evidence must be complete")
            digest(baseline, "baseline_artifact_sha256", required=True)
            positive(
                self.observed_value_microunits,
                "observed_value_microunits",
            )
            if self.regression_ppm != 0:
                raise ValueError("performance baseline capture regression must be zero")
            return
        if baseline is None:
            if any(value is not None for value in measurements):
                raise ValueError("performance measurements require a baseline")
            return
        digest(baseline, "baseline_artifact_sha256", required=True)
        if all(value is None for value in measurements) and self.status is not RuntimeDiagnosticStatus.PASSED:
            return
        if any(value is None for value in measurements):
            raise ValueError("performance comparison evidence must be complete")
        positive(self.observed_value_microunits, "observed_value_microunits", allow_zero=True)
        if not isinstance(self.regression_ppm, int):
            raise ValueError("regression_ppm must be an integer")


def validate_runtime_diagnostic_receipt(
    request: RuntimeDiagnosticRequest,
    receipt: RuntimeDiagnosticReceipt,
) -> None:
    """Validate receipt identity, bounds, artifacts, and performance policy."""
    expected = (
        request.request_id,
        request.task_id,
        request.candidate_id,
        request.signed_recipe_id,
        request.signed_recipe_version,
        request.recipe_payload_sha256,
    )
    actual = (
        receipt.request_id,
        receipt.task_id,
        receipt.candidate_id,
        receipt.signed_recipe_id,
        receipt.signed_recipe_version,
        receipt.recipe_payload_sha256,
    )
    if actual != expected:
        raise ValueError("runtime diagnostic receipt does not match its request")
    elapsed = (receipt.completed_at - receipt.started_at).total_seconds()
    if elapsed > request.limits.wall_seconds:
        raise ValueError("runtime diagnostic receipt exceeds its wall limit")
    if sum(item.size_bytes for item in receipt.artifacts) > request.limits.artifact_bytes:
        raise ValueError("runtime diagnostic artifacts exceed their byte limit")
    if not {item.kind for item in receipt.artifacts}.issubset(set(request.artifact_kinds)):
        raise ValueError("runtime diagnostic receipt contains an unrequested artifact kind")
    if receipt.baseline_artifact_sha256 != request.baseline_artifact_sha256:
        if not (
            request.performance_mode is RuntimePerformanceMode.BASELINE_CAPTURE
            and receipt.baseline_artifact_sha256 in {
                item.sha256 for item in receipt.artifacts
            }
        ):
            raise ValueError("runtime diagnostic receipt baseline does not match its request")
    if receipt.performance_mode is not request.performance_mode:
        raise ValueError("runtime diagnostic receipt performance mode differs")
    if (
        request.maximum_regression_ppm is not None
        and receipt.status is RuntimeDiagnosticStatus.PASSED
        and receipt.regression_ppm is not None
        and receipt.regression_ppm > request.maximum_regression_ppm
    ):
        raise ValueError("performance regression exceeds the passing threshold")
