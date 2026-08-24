"""Bounded Bubblewrap execution and candidate storage for text diagnostics."""

import hashlib
import os
import re
from decimal import Decimal, InvalidOperation
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fam_os.adapters.bubblewrap.engineering import EngineeringSandboxAdapter
from fam_os.adapters.bubblewrap.process import ProcessLauncher, SubprocessProcessLauncher
from fam_os.core.engineering.diagnostic_policy import RuntimeDiagnosticRecipePolicy
from fam_os.core.engineering.diagnostic_redaction import (
    DeterministicDiagnosticTextSanitizer,
    SanitizedDiagnosticText,
)
from fam_os.core.engineering.diagnostics import (
    DiagnosticArtifactKind,
    RuntimeDiagnosticArtifact,
    RuntimeDiagnosticKind,
    RuntimeDiagnosticReceipt,
    RuntimeDiagnosticRequest,
    RuntimeDiagnosticStatus,
    RuntimePerformanceMode,
    validate_runtime_diagnostic_receipt,
)
from fam_os.core.engineering.execution import EngineeringSandboxProfile
from fam_os.core.engineering.transactions import CandidateWorkspace
from fam_os.verification.sandbox import IsolationLevel, SandboxLimits, SandboxStatus


class PosixTimeMetricParser:
    _REAL = re.compile(r"(?m)^real\s+([0-9]+(?:\.[0-9]+)?)\s*$")

    def parse_microunits(self, stderr: str) -> int:
        matches = self._REAL.findall(stderr)
        if len(matches) != 1:
            raise ValueError("performance diagnostic requires one POSIX real-time metric")
        try:
            value = int(Decimal(matches[0]) * 1_000_000)
        except (InvalidOperation, ValueError) as error:
            raise ValueError("performance diagnostic metric is invalid") from error
        if value < 0:
            raise ValueError("performance diagnostic metric cannot be negative")
        return value


class CandidateDiagnosticArtifactStore:
    def store(
        self,
        candidate: CandidateWorkspace,
        request_id: str,
        kind: DiagnosticArtifactKind,
        content: bytes,
    ) -> RuntimeDiagnosticArtifact:
        root = Path(candidate.candidate_workspace).resolve(strict=True)
        if root.is_symlink() or not root.is_dir():
            raise PermissionError("diagnostic candidate root is invalid")
        relative = Path(".fam") / "diagnostics" / request_id / f"{kind.value}.txt"
        parent = root / relative.parent
        self._mkdirs(root, parent)
        target = root / relative
        descriptor = os.open(
            target,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
        )
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
        except Exception:
            target.unlink(missing_ok=True)
            raise
        return RuntimeDiagnosticArtifact(
            relative.as_posix(), kind, "text/plain; charset=utf-8",
            hashlib.sha256(content).hexdigest(), len(content), True,
        )

    @staticmethod
    def _mkdirs(root: Path, parent: Path) -> None:
        current = root
        for part in parent.relative_to(root).parts:
            current /= part
            if current.exists() and current.is_symlink():
                raise PermissionError("diagnostic artifact path contains a symlink")
            current.mkdir(mode=0o700, exist_ok=True)


class BubblewrapRuntimeDiagnosticAdapter:
    def __init__(
        self,
        policy: RuntimeDiagnosticRecipePolicy,
        sandbox: EngineeringSandboxAdapter,
        launcher: ProcessLauncher | None = None,
        sanitizer: DeterministicDiagnosticTextSanitizer | None = None,
        store: CandidateDiagnosticArtifactStore | None = None,
        metric_parser: PosixTimeMetricParser | None = None,
        clock=None,
    ) -> None:
        self._policy = policy
        self._sandbox = sandbox
        self._launcher = launcher or SubprocessProcessLauncher()
        self._sanitizer = sanitizer or DeterministicDiagnosticTextSanitizer()
        self._store = store or CandidateDiagnosticArtifactStore()
        self._metric_parser = metric_parser or PosixTimeMetricParser()
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def run(
        self,
        request: RuntimeDiagnosticRequest,
        candidate: CandidateWorkspace,
        profile: EngineeringSandboxProfile,
        *,
        authorization_decision_ids: tuple[str, ...],
    ) -> RuntimeDiagnosticReceipt:
        root = self._validate_scope(request, candidate, profile)
        recipe = self._policy.admit(request)
        argv = self._policy.resolve_argv(request, recipe)
        self._safe_target(root, request.target_argv[0])
        command = self._sandbox.build_command(root, recipe, profile, argv)
        limits = SandboxLimits(
            wall_seconds=float(request.limits.wall_seconds),
            memory_bytes=request.limits.memory_bytes,
            cpu_seconds=request.limits.cpu_seconds,
            file_bytes=request.limits.temporary_file_bytes,
            open_files=64,
            processes=request.limits.process_limit,
            output_bytes=request.limits.output_bytes,
            unbounded_virtual_address_space=request.limits.unbounded_virtual_address_space,
        )
        started = self._clock()
        result = self._launcher.run(
            command, limits, profile.sanitized_environment,
            IsolationLevel.BUBBLEWRAP,
        )
        completed = self._clock()
        artifacts, sanitizer_ids = self._artifacts(request, candidate, result)
        comparison = self._comparison(request, result, artifacts)
        status = self._status(request, result.status, result.exit_code, comparison)
        receipt = RuntimeDiagnosticReceipt(
            f"diagnostic-receipt-{uuid4().hex}", request.request_id,
            request.task_id, request.candidate_id, request.signed_recipe_id,
            request.signed_recipe_version, request.recipe_payload_sha256,
            profile.profile_id, started, completed, status, result.exit_code,
            _digest(result.stdout), _digest(result.stderr), artifacts, (),
            ("bubblewrap-unshare-all", "cgroup-v2-systemd", "bounded-rlimits", *sanitizer_ids),
            authorization_decision_ids,
            baseline_artifact_sha256=comparison[0],
            observed_value_microunits=comparison[1],
            regression_ppm=comparison[2],
            diagnostic=result.reason[-1024:],
            performance_mode=request.performance_mode,
        )
        validate_runtime_diagnostic_receipt(request, receipt)
        return receipt

    @staticmethod
    def _safe_target(root: Path, relative: str) -> Path:
        current = root
        for part in Path(relative).parts:
            current /= part
            if current.is_symlink():
                raise PermissionError("diagnostic target path contains a symlink")
        target = current.resolve(strict=True)
        if root not in target.parents or not target.is_file():
            raise PermissionError("diagnostic target escapes the candidate or is not regular")
        return target

    def _validate_scope(self, request, candidate, profile) -> Path:
        if request.candidate_id != candidate.candidate_id:
            raise PermissionError("diagnostic request candidate is mismatched")
        if request.network_mode is not profile.network_mode:
            raise PermissionError("diagnostic request and sandbox network policies differ")
        profile_environment = {key for key, _value in profile.sanitized_environment}
        if profile_environment - set(request.allowed_environment_keys):
            raise PermissionError("diagnostic sandbox widens the request environment")
        profile_values = (
            profile.wall_seconds, profile.cpu_seconds, profile.memory_bytes,
            profile.process_limit, profile.output_bytes, profile.artifact_bytes,
        )
        request_values = (
            request.limits.wall_seconds, request.limits.cpu_seconds,
            request.limits.memory_bytes, request.limits.process_limit,
            request.limits.output_bytes, request.limits.temporary_file_bytes,
        )
        if any(actual > maximum for actual, maximum in zip(profile_values, request_values)):
            raise PermissionError("diagnostic sandbox profile widens request limits")
        return Path(candidate.candidate_workspace).resolve(strict=True)

    def _artifacts(self, request, candidate, result):
        if result.status is not SandboxStatus.COMPLETED:
            return (), ()
        combined = result.stdout + ("\n" if result.stdout and result.stderr else "") + result.stderr
        sanitized = self._sanitizer.sanitize(combined, request.limits.artifact_bytes)
        artifact = self._store.store(
            candidate, request.request_id, request.artifact_kinds[0], sanitized.content,
        )
        return (artifact,), (sanitized.sanitizer_evidence_id,)

    def _comparison(self, request, result, artifacts):
        if request.kind is not RuntimeDiagnosticKind.PERFORMANCE_REGRESSION:
            return None, None, None
        if result.status is not SandboxStatus.COMPLETED or result.exit_code != 0:
            return request.baseline_artifact_sha256, None, None
        observed = self._metric_parser.parse_microunits(result.stderr)
        if request.performance_mode is RuntimePerformanceMode.BASELINE_CAPTURE:
            if not artifacts:
                raise ValueError("performance baseline capture lacks an artifact")
            return artifacts[0].sha256, observed, 0
        baseline = request.baseline_value_microunits
        regression = ((observed - baseline) * 1_000_000) // baseline
        return request.baseline_artifact_sha256, observed, regression

    @staticmethod
    def _status(request, status, exit_code, comparison):
        if status is SandboxStatus.COMPLETED:
            if exit_code == 69:
                return RuntimeDiagnosticStatus.UNAVAILABLE
            if exit_code != 0:
                return RuntimeDiagnosticStatus.FAILED
            if (
                request.maximum_regression_ppm is not None
                and comparison[2] is not None
                and comparison[2] > request.maximum_regression_ppm
            ):
                return RuntimeDiagnosticStatus.FAILED
            return RuntimeDiagnosticStatus.PASSED
        if status is SandboxStatus.TIMED_OUT:
            return RuntimeDiagnosticStatus.CANCELLED
        return RuntimeDiagnosticStatus.UNAVAILABLE


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
