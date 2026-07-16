"""Versioned expert quality, repair, conformance, and resource evidence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from fam_os.experts.registry_contracts import ExpertPackageCoordinate
from fam_os.registry.package import ArtifactDigest


EXPERT_BENCHMARK_METADATA_VERSION = "fam.expert.benchmark/v1alpha1"


class BenchmarkAttemptKind(StrEnum):
    INITIAL = "initial"
    REPAIR = "repair"
    ESCALATION = "escalation"


class VerifierContextDisclosure(StrEnum):
    NONE = "none"
    EXAMPLES = "examples"
    TRUSTED_TESTS_AND_EXAMPLES = "trusted_tests_and_examples"


class BenchmarkOutcome(StrEnum):
    VERIFIED_INITIAL = "verified_initial"
    VERIFIED_AFTER_REPAIR = "verified_after_repair"
    VERIFIED_AFTER_ESCALATION = "verified_after_escalation"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ExpertBenchmarkAttempt:
    attempt_index: int
    kind: BenchmarkAttemptKind
    model_ref: str
    verifier_context_disclosure: VerifierContextDisclosure
    disclosed_context_digest: ArtifactDigest | None
    verification_passed: bool
    conformance_failure_codes: tuple[str, ...]
    wall_seconds: float
    prompt_tokens: int
    output_tokens: int

    def __post_init__(self) -> None:
        if self.attempt_index < 0:
            raise ValueError("benchmark attempt index must not be negative")
        _require_text(self.model_ref, "model_ref")
        if self.kind is BenchmarkAttemptKind.INITIAL and self.verifier_context_disclosure is not VerifierContextDisclosure.NONE:
            raise ValueError("initial attempts cannot disclose verifier context")
        disclosed = self.verifier_context_disclosure is not VerifierContextDisclosure.NONE
        if disclosed != (self.disclosed_context_digest is not None):
            raise ValueError("disclosed verifier context requires its exact digest")
        if self.disclosed_context_digest and self.disclosed_context_digest.algorithm != "sha256":
            raise ValueError("disclosed context digest must use SHA-256")
        _require_unique_text(self.conformance_failure_codes, "conformance failures", True)
        if self.verification_passed and self.conformance_failure_codes:
            raise ValueError("a passing attempt cannot retain conformance failures")
        if self.wall_seconds < 0 or self.prompt_tokens < 0 or self.output_tokens < 0:
            raise ValueError("attempt measurements must not be negative")


@dataclass(frozen=True, slots=True)
class ExpertBenchmarkResources:
    cpu_usage_microseconds: int | None
    peak_system_memory_bytes: int | None
    max_accelerator_memory_bytes: int | None
    model_resident_bytes: int | None
    model_accelerator_bytes: int | None
    storage_read_bytes: int | None
    storage_write_bytes: int | None
    unavailable_measurements: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        values = _resource_values(self)
        if any(value is not None and value < 0 for value in values.values()):
            raise ValueError("benchmark resource measurements must not be negative")
        _require_unique_text(self.unavailable_measurements, "unavailable measurements", True)
        if not set(self.unavailable_measurements).issubset(values):
            raise ValueError("unknown unavailable resource measurement")
        for name, value in values.items():
            if (value is None) != (name in self.unavailable_measurements):
                raise ValueError("resource availability must exactly match missing values")


@dataclass(frozen=True, slots=True)
class ExpertBenchmarkRun:
    run_id: str
    suite_id: str
    suite_version: str
    coordinate: ExpertPackageCoordinate
    expert_id: str
    validation_profile_id: str
    acceptance_policy_id: str
    captured_at: datetime
    outcome: BenchmarkOutcome
    strict_requirement_ids: tuple[str, ...]
    attempts: tuple[ExpertBenchmarkAttempt, ...]
    resources: ExpertBenchmarkResources
    raw_evidence_digest: ArtifactDigest
    contract_version: str = EXPERT_BENCHMARK_METADATA_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != EXPERT_BENCHMARK_METADATA_VERSION:
            raise ValueError("unsupported expert benchmark contract_version")
        for name in (
            "run_id", "suite_id", "suite_version", "expert_id",
            "validation_profile_id", "acceptance_policy_id",
        ):
            _require_text(getattr(self, name), name)
        if self.captured_at.tzinfo is None or self.captured_at.utcoffset() is None:
            raise ValueError("benchmark captured_at must be timezone-aware")
        _require_unique_text(self.strict_requirement_ids, "strict requirements", False)
        if not self.attempts:
            raise ValueError("benchmark run requires attempts")
        indexes = tuple(item.attempt_index for item in self.attempts)
        if indexes != tuple(range(len(self.attempts))):
            raise ValueError("benchmark attempt indexes must be contiguous")
        if self.attempts[0].kind is not BenchmarkAttemptKind.INITIAL:
            raise ValueError("benchmark run must begin with an initial attempt")
        _require_outcome(self.outcome, self.attempts)
        if self.raw_evidence_digest.algorithm != "sha256":
            raise ValueError("raw benchmark evidence digest must use SHA-256")


def require_full_host_evidence(run: ExpertBenchmarkRun) -> None:
    if run.validation_profile_id != "full-reference-workstation":
        raise ValueError("strong-model regression requires the full-reference workstation")
    if run.resources.unavailable_measurements:
        raise ValueError("full-host benchmark requires every resource measurement")


def _require_outcome(outcome, attempts):
    passed = tuple(item for item in attempts if item.verification_passed)
    if outcome is BenchmarkOutcome.FAILED:
        if passed:
            raise ValueError("failed benchmark cannot contain a passing attempt")
        return
    if len(passed) != 1 or passed[0] is not attempts[-1]:
        raise ValueError("verified benchmark must end at its only passing attempt")
    expected = {
        BenchmarkOutcome.VERIFIED_INITIAL: BenchmarkAttemptKind.INITIAL,
        BenchmarkOutcome.VERIFIED_AFTER_REPAIR: BenchmarkAttemptKind.REPAIR,
        BenchmarkOutcome.VERIFIED_AFTER_ESCALATION: BenchmarkAttemptKind.ESCALATION,
    }[outcome]
    if passed[0].kind is not expected:
        raise ValueError("benchmark outcome does not match passing attempt kind")


def _resource_values(value):
    return {
        "cpu": value.cpu_usage_microseconds,
        "ram": value.peak_system_memory_bytes,
        "vram": value.max_accelerator_memory_bytes,
        "model_resident": value.model_resident_bytes,
        "model_accelerator": value.model_accelerator_bytes,
        "storage_read": value.storage_read_bytes,
        "storage_write": value.storage_write_bytes,
    }


def _require_unique_text(values, name, allow_empty):
    if not allow_empty and not values:
        raise ValueError(f"{name} must not be empty")
    if len(set(values)) != len(values) or any(not value.strip() for value in values):
        raise ValueError(f"{name} values must be non-empty and unique")


def _require_text(value, name):
    if not value.strip():
        raise ValueError(f"{name} must not be empty")
