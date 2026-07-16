"""Cross-family benchmark suite and immutable case-result contracts."""

from dataclasses import dataclass
from enum import StrEnum

from fam_os.experts.manifest import ExpertTier


MIXED_BENCHMARK_CONTRACT_VERSION = "fam.expert.mixed-benchmark/v1alpha1"


class BenchmarkTaskFamily(StrEnum):
    KERNEL_ONLY = "kernel_only"
    CODE = "code"
    MATHEMATICS = "mathematics"
    RETRIEVAL = "retrieval"
    APPLICATION = "application"


@dataclass(frozen=True, slots=True)
class MixedBenchmarkCase:
    case_id: str
    family: BenchmarkTaskFamily
    capability_id: str
    acceptance_id: str
    fixture_sha256: str
    named_regression: bool = False

    def __post_init__(self) -> None:
        if not all(value.strip() for value in (
            self.case_id, self.capability_id, self.acceptance_id,
        )):
            raise ValueError("benchmark case IDs must not be empty")
        _digest(self.fixture_sha256)


@dataclass(frozen=True, slots=True)
class MixedBenchmarkSuite:
    suite_id: str
    suite_version: str
    cases: tuple[MixedBenchmarkCase, ...]
    contract_version: str = MIXED_BENCHMARK_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if not self.suite_id.strip() or not self.suite_version.strip() or not self.cases:
            raise ValueError("mixed benchmark identity and cases are required")
        if len({case.case_id for case in self.cases}) != len(self.cases):
            raise ValueError("mixed benchmark case IDs must be unique")
        required = set(BenchmarkTaskFamily)
        if {case.family for case in self.cases} != required:
            raise ValueError("mixed benchmark must cover every task family")


@dataclass(frozen=True, slots=True)
class MixedBenchmarkCaseResult:
    case_id: str
    passed: bool
    acceptance_id: str
    evidence_sha256: str
    expert_id: str | None = None
    expert_tier: ExpertTier | None = None
    model_ref: str | None = None

    def __post_init__(self) -> None:
        _digest(self.evidence_sha256)
        model_used = self.expert_id is not None or self.expert_tier is not None or self.model_ref is not None
        if model_used and not all((self.expert_id, self.expert_tier, self.model_ref)):
            raise ValueError("model benchmark evidence requires complete expert identity")


@dataclass(frozen=True, slots=True)
class StrongRegressionRunRef:
    model_ref: str
    expert_id: str
    package_artifact_sha256: str
    report_sha256: str
    verified: bool

    def __post_init__(self) -> None:
        if not self.model_ref.strip() or not self.expert_id.strip():
            raise ValueError("strong regression model identity is required")
        _digest(self.package_artifact_sha256)
        _digest(self.report_sha256)


@dataclass(frozen=True, slots=True)
class MixedBenchmarkReport:
    suite_id: str
    suite_version: str
    results: tuple[MixedBenchmarkCaseResult, ...]
    strong_regressions: tuple[StrongRegressionRunRef, ...]
    passed: bool
    contract_version: str = MIXED_BENCHMARK_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if len({result.case_id for result in self.results}) != len(self.results):
            raise ValueError("mixed benchmark result case IDs must be unique")
        if self.passed != bool(self.results and all(item.passed for item in self.results)):
            raise ValueError("mixed benchmark pass must equal all case outcomes")
        if len({item.model_ref for item in self.strong_regressions}) != len(self.strong_regressions):
            raise ValueError("strong regression model references must be unique")


def validate_mixed_report(suite: MixedBenchmarkSuite, report: MixedBenchmarkReport) -> None:
    if (suite.suite_id, suite.suite_version) != (report.suite_id, report.suite_version):
        raise ValueError("mixed benchmark report identifies the wrong suite")
    cases = {case.case_id: case for case in suite.cases}
    if set(cases) != {result.case_id for result in report.results}:
        raise ValueError("mixed benchmark report must contain every case exactly once")
    for result in report.results:
        case = cases[result.case_id]
        if result.acceptance_id != case.acceptance_id:
            raise ValueError("mixed benchmark result acceptance policy mismatch")
        if case.family is BenchmarkTaskFamily.KERNEL_ONLY and result.expert_id is not None:
            raise ValueError("kernel-only benchmark cannot use an expert")
    required_models = {"laguna-xs.2:q4_K_M", "gemma4:26b"}
    if {item.model_ref for item in report.strong_regressions} != required_models:
        raise ValueError("mixed benchmark requires independent Laguna and Gemma regressions")


def _digest(value: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError("benchmark digest must be lowercase SHA-256")
