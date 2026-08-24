"""Deterministic natural-intent selection for signed runtime diagnostics."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation

from fam_os.core.engineering.diagnostics import (
    DiagnosticArtifactKind, RuntimeDiagnosticKind, RuntimeDiagnosticLimits,
    RuntimeDiagnosticPhase, RuntimeDiagnosticRequest,
    RuntimePerformanceMode,
)
from fam_os.core.engineering._validation import digest, positive
from fam_os.core.engineering.execution import (
    SandboxNetworkMode, ToolRecipePurpose,
)


_PATTERNS = (
    (RuntimeDiagnosticKind.CRASH_DUMP, re.compile(r"\b(?:crash|core) dumps?\b")),
    (RuntimeDiagnosticKind.STACK_TRACE, re.compile(r"\b(?:stack trace|backtrace|debug crash)\b")),
    (RuntimeDiagnosticKind.RACE_DETECTION, re.compile(r"\b(?:data race|race detection|thread ?sanitizer|tsan)\b")),
    (RuntimeDiagnosticKind.LEAK_DETECTION, re.compile(r"\b(?:memory leak|leak detection|leak ?sanitizer|lsan)\b")),
    (RuntimeDiagnosticKind.CPU_PROFILE, re.compile(r"\b(?:cpu profil(?:e|ing)|profile cpu)\b")),
    (RuntimeDiagnosticKind.MEMORY_PROFILE, re.compile(r"\b(?:memory profil(?:e|ing)|profile memory|memory usage)\b")),
    (RuntimeDiagnosticKind.PERFORMANCE_REGRESSION, re.compile(r"\b(?:performance regression|benchmark regression|compare performance)\b")),
    (RuntimeDiagnosticKind.TRACE, re.compile(r"\b(?:(?:local|system call|syscall) trac(?:e|ing)|trace execution)\b")),
)

_PURPOSES = {
    RuntimeDiagnosticKind.STACK_TRACE: ToolRecipePurpose.STACK_TRACE,
    RuntimeDiagnosticKind.CRASH_DUMP: ToolRecipePurpose.CRASH_DUMP,
    RuntimeDiagnosticKind.TRACE: ToolRecipePurpose.TRACE,
    RuntimeDiagnosticKind.CPU_PROFILE: ToolRecipePurpose.CPU_PROFILE,
    RuntimeDiagnosticKind.MEMORY_PROFILE: ToolRecipePurpose.MEMORY_PROFILE,
    RuntimeDiagnosticKind.RACE_DETECTION: ToolRecipePurpose.RACE_DETECTION,
    RuntimeDiagnosticKind.LEAK_DETECTION: ToolRecipePurpose.LEAK_DETECTION,
    RuntimeDiagnosticKind.PERFORMANCE_REGRESSION: ToolRecipePurpose.PERFORMANCE_REGRESSION,
}

_ARTIFACTS = {
    RuntimeDiagnosticKind.STACK_TRACE: DiagnosticArtifactKind.STACK_TRACE,
    RuntimeDiagnosticKind.CRASH_DUMP: DiagnosticArtifactKind.CRASH_DUMP,
    RuntimeDiagnosticKind.TRACE: DiagnosticArtifactKind.TRACE,
    RuntimeDiagnosticKind.CPU_PROFILE: DiagnosticArtifactKind.PROFILE,
    RuntimeDiagnosticKind.MEMORY_PROFILE: DiagnosticArtifactKind.PROFILE,
    RuntimeDiagnosticKind.RACE_DETECTION: DiagnosticArtifactKind.RACE_REPORT,
    RuntimeDiagnosticKind.LEAK_DETECTION: DiagnosticArtifactKind.LEAK_REPORT,
    RuntimeDiagnosticKind.PERFORMANCE_REGRESSION: DiagnosticArtifactKind.PERFORMANCE_SAMPLE,
}


@dataclass(frozen=True, slots=True)
class RuntimePerformanceBaseline:
    artifact_sha256: str
    value_microunits: int
    maximum_regression_ppm: int

    def __post_init__(self) -> None:
        digest(self.artifact_sha256, "artifact_sha256", required=True)
        positive(self.value_microunits, "value_microunits")
        positive(
            self.maximum_regression_ppm,
            "maximum_regression_ppm", allow_zero=True,
        )


class RuntimeDiagnosticIntentPolicy:
    """Translate exact words and repository facts; never accept recipe coordinates."""

    def __init__(self, catalog) -> None:
        self._catalog = catalog

    def requested_kinds(self, intent: str) -> tuple[RuntimeDiagnosticKind, ...]:
        normalized = " ".join(intent.casefold().split())
        if "distributed trace" in normalized or "distributed tracing" in normalized:
            raise LookupError("distributed tracing requires a composed service environment")
        values = [kind for kind, pattern in _PATTERNS if pattern.search(normalized)]
        if (
            not {
                RuntimeDiagnosticKind.CPU_PROFILE,
                RuntimeDiagnosticKind.MEMORY_PROFILE,
            }.intersection(values)
            and re.search(r"\bprofil(?:e|ing)\b", normalized)
        ):
            values.append(RuntimeDiagnosticKind.CPU_PROFILE)
        if not values and re.search(r"\bdebug(?:ger|ging)?\b", normalized):
            values.append(RuntimeDiagnosticKind.STACK_TRACE)
        return tuple(values)

    def plan(
        self, definition, candidate, entries, preferred_paths, *,
        phase: RuntimeDiagnosticPhase,
        session_id: str, principal_id: str, now: datetime,
        baselines: dict[str, RuntimePerformanceBaseline] | None = None,
    ) -> tuple[RuntimeDiagnosticRequest, ...]:
        kinds = self.requested_kinds(definition.task.intent)
        if not kinds:
            return ()
        if candidate.created_at > now:
            raise ValueError("runtime diagnostic candidate creation is in the future")
        recipes = _unique_recipes(
            self._catalog, tuple(_PURPOSES[kind] for kind in kinds),
        )
        ordered = _ordered_entries(entries, preferred_paths)
        requests = []
        for kind in kinds:
            target = _target(kind, ordered)
            recipe = recipes[_PURPOSES[kind]]
            baseline = None if baselines is None else baselines.get(target.path)
            if kind is RuntimeDiagnosticKind.PERFORMANCE_REGRESSION and baseline is None:
                raise LookupError("performance regression requires an exact captured baseline")
            limits = _limits(definition.task.max_wall_seconds, kind)
            identity = hashlib.sha256(
                f"{definition.task.task_id}:{candidate.candidate_id}:{phase.value}:"
                f"{kind.value}:{target.path}:{recipe.payload_sha256}".encode()
            ).hexdigest()[:32]
            requests.append(RuntimeDiagnosticRequest(
                f"runtime-diagnostic-{identity}", definition.task.task_id,
                candidate.candidate_id, definition.task.grant_id,
                principal_id, session_id, phase, recipe.recipe_id,
                recipe.recipe_version, recipe.payload_sha256, kind,
                (target.path,), recipe.allowed_environment_keys,
                (_ARTIFACTS[kind],), limits, recipe.network_mode, (),
                candidate.created_at,
                None if baseline is None else baseline.artifact_sha256,
                None if baseline is None else baseline.value_microunits,
                None if baseline is None else baseline.maximum_regression_ppm,
                performance_mode=(
                    RuntimePerformanceMode.COMPARISON
                    if kind is RuntimeDiagnosticKind.PERFORMANCE_REGRESSION
                    else RuntimePerformanceMode.NOT_APPLICABLE
                ),
            ))
        return tuple(requests)

    def plan_performance_baseline(
        self, definition, candidate, entries, preferred_paths, *,
        session_id: str, principal_id: str, now: datetime,
    ) -> tuple[RuntimeDiagnosticRequest, ...]:
        if RuntimeDiagnosticKind.PERFORMANCE_REGRESSION not in self.requested_kinds(
            definition.task.intent
        ):
            return ()
        recipe = _unique_recipes(
            self._catalog, (ToolRecipePurpose.PERFORMANCE_REGRESSION,),
        )[ToolRecipePurpose.PERFORMANCE_REGRESSION]
        target = _target(
            RuntimeDiagnosticKind.PERFORMANCE_REGRESSION,
            _ordered_entries(entries, preferred_paths),
        )
        limits = _limits(
            definition.task.max_wall_seconds,
            RuntimeDiagnosticKind.PERFORMANCE_REGRESSION,
        )
        identity = hashlib.sha256(
            f"{definition.task.task_id}:{candidate.candidate_id}:baseline:"
            f"{target.path}:{recipe.payload_sha256}".encode()
        ).hexdigest()[:32]
        return (RuntimeDiagnosticRequest(
            f"runtime-diagnostic-{identity}", definition.task.task_id,
            candidate.candidate_id, definition.task.grant_id, principal_id,
            session_id, RuntimeDiagnosticPhase.BASELINE, recipe.recipe_id,
            recipe.recipe_version, recipe.payload_sha256,
            RuntimeDiagnosticKind.PERFORMANCE_REGRESSION, (target.path,),
            recipe.allowed_environment_keys,
            (DiagnosticArtifactKind.PERFORMANCE_SAMPLE,), limits,
            recipe.network_mode, (), candidate.created_at, None, None,
            _regression_threshold(definition.task.intent),
            performance_mode=RuntimePerformanceMode.BASELINE_CAPTURE,
        ),)


def _unique_recipes(catalog, purposes):
    """Fail closed unless each requested purpose has exactly one signed recipe."""
    selected = {}
    for recipe in catalog.matching_purposes(purposes):
        if recipe.purpose in selected:
            raise LookupError(
                "multiple installed signed runtime diagnostic recipes are ambiguous"
            )
        selected[recipe.purpose] = recipe
    if set(selected) != set(purposes):
        raise LookupError("an installed signed runtime diagnostic recipe is unavailable")
    return selected


def _ordered_entries(entries, preferred_paths):
    files = {item.path: item for item in entries if item.kind.value == "file"}
    paths = tuple(dict.fromkeys((*preferred_paths, *sorted(files))))
    return tuple(files[path] for path in paths if path in files)


def _target(kind, entries):
    for item in entries:
        if kind in {RuntimeDiagnosticKind.CPU_PROFILE, RuntimeDiagnosticKind.MEMORY_PROFILE}:
            compatible = item.path.endswith(".py")
        elif kind in {RuntimeDiagnosticKind.RACE_DETECTION, RuntimeDiagnosticKind.LEAK_DETECTION}:
            compatible = item.path.endswith(".c")
        elif kind in {
            RuntimeDiagnosticKind.STACK_TRACE,
            RuntimeDiagnosticKind.CRASH_DUMP,
            RuntimeDiagnosticKind.TRACE,
            RuntimeDiagnosticKind.PERFORMANCE_REGRESSION,
        }:
            compatible = item.path.endswith(".py") or item.executable
        else:
            compatible = item.executable
        if compatible:
            return item
    raise LookupError(f"no compatible candidate target exists for {kind.value}")


def _limits(maximum_wall_seconds: int, kind: RuntimeDiagnosticKind):
    wall = min(maximum_wall_seconds, 60)
    sparse = kind in {
        RuntimeDiagnosticKind.STACK_TRACE, RuntimeDiagnosticKind.CRASH_DUMP,
        RuntimeDiagnosticKind.RACE_DETECTION, RuntimeDiagnosticKind.LEAK_DETECTION,
    }
    return RuntimeDiagnosticLimits(
        wall, min(wall, 30), 512 * 1024**2, 32, 1_048_576,
        4_194_304, 10_000, 64 * 1024**2, sparse,
    )


def _regression_threshold(intent: str) -> int:
    values = re.findall(
        r"(?:no more than|maximum|max|under|within)?\s*([0-9]{1,3}(?:\.[0-9]+)?)\s*%\s*(?:performance )?regression",
        intent.casefold(),
    )
    if not values:
        return 50_000
    try:
        value = Decimal(values[-1])
    except InvalidOperation as error:
        raise ValueError("performance regression percentage is invalid") from error
    if value < 0 or value > 100:
        raise ValueError("performance regression percentage is outside policy")
    return int(value * 10_000)
