"""Deterministic advisory micro-experts for early local classification."""

from dataclasses import dataclass


MICRO_EXPERT_CONTRACT_VERSION = "fam.expert.micro-advice/v1alpha1"


@dataclass(frozen=True, slots=True)
class MicroExpertAdvice:
    expert_id: str
    label: str
    confidence_millionths: int
    reason_codes: tuple[str, ...]
    advisory_only: bool = True
    contract_version: str = MICRO_EXPERT_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if not self.expert_id.strip() or not self.label.strip() or not self.reason_codes:
            raise ValueError("micro-expert advice requires identity, label, and reasons")
        if not 0 <= self.confidence_millionths <= 1_000_000:
            raise ValueError("micro-expert confidence must be a fixed-point probability")
        if not self.advisory_only:
            raise ValueError("micro-expert advice cannot carry execution authority")


@dataclass(frozen=True, slots=True)
class MicroExpertBenchmarkResult:
    expert_id: str
    case_count: int
    correct_count: int
    accuracy_millionths: int
    fixture_sha256: str
    contract_version: str = MICRO_EXPERT_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.case_count <= 0 or not 0 <= self.correct_count <= self.case_count:
            raise ValueError("micro benchmark counts are invalid")
        expected = self.correct_count * 1_000_000 // self.case_count
        if self.accuracy_millionths != expected:
            raise ValueError("micro benchmark accuracy must match counts")
        if len(self.fixture_sha256) != 64 or any(character not in "0123456789abcdef" for character in self.fixture_sha256):
            raise ValueError("micro benchmark fixture must use lowercase SHA-256")


@dataclass(frozen=True, slots=True)
class MicroExpertBenchmarkReport:
    suite_id: str
    results: tuple[MicroExpertBenchmarkResult, ...]
    minimum_accuracy_millionths: int
    passed: bool
    contract_version: str = MICRO_EXPERT_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if len({item.expert_id for item in self.results}) != 4:
            raise ValueError("micro benchmark requires four unique experts")
        expected = all(item.accuracy_millionths >= self.minimum_accuracy_millionths for item in self.results)
        if self.passed != expected:
            raise ValueError("micro benchmark pass must match threshold")


class RoutingMicroExpert:
    expert_id = "expert.micro.routing-v1"

    def advise(self, text: str) -> MicroExpertAdvice:
        return _keyword_advice(self.expert_id, text, _ROUTES, "language.respond")


class LanguageDetectionMicroExpert:
    expert_id = "expert.micro.language-detection-v1"

    def advise(self, text: str) -> MicroExpertAdvice:
        lowered = text.lower()
        if any("\u0400" <= character <= "\u04ff" for character in text):
            return _advice(self.expert_id, "bg", 990_000, "script.cyrillic")
        spanish = sum(word in lowered.split() for word in ("el", "la", "que", "para", "hola"))
        if spanish:
            return _advice(self.expert_id, "es", min(990_000, 700_000 + spanish * 50_000), "token.spanish")
        return _advice(self.expert_id, "en", 700_000, "default.latin-english")


class SafetyMicroExpert:
    expert_id = "expert.micro.safety-v1"

    def advise(self, text: str) -> MicroExpertAdvice:
        lowered = text.lower()
        matches = tuple(code for phrase, code in _RISKS if phrase in lowered)
        if matches:
            return MicroExpertAdvice(self.expert_id, "review_required", 980_000, matches)
        return _advice(self.expert_id, "no_known_pattern", 650_000, "pattern.none")


class ComplexityMicroExpert:
    expert_id = "expert.micro.complexity-v1"

    def advise(self, text: str) -> MicroExpertAdvice:
        lowered = text.lower()
        score = min(10, len(text.split()) // 35 + sum(token in lowered for token in _COMPLEXITY))
        if score >= 5:
            return _advice(self.expert_id, "escalation", 800_000, "score.high")
        if score >= 2:
            return _advice(self.expert_id, "economical", 750_000, "score.medium")
        return _advice(self.expert_id, "micro_or_kernel", 800_000, "score.low")


def _keyword_advice(expert_id, text, groups, fallback):
    lowered = text.lower()
    ranked = tuple((sum(token in lowered for token in tokens), label) for label, tokens in groups)
    score, label = max(ranked, key=lambda item: (item[0], item[1]))
    if score == 0:
        label = fallback
    return _advice(expert_id, label, 650_000 + min(score, 3) * 100_000, f"keywords.{label}")


def _advice(expert_id, label, confidence, reason):
    return MicroExpertAdvice(expert_id, label, confidence, (reason,))


_ROUTES = (
    ("code.generate.python", ("python", "code", "function", "test")),
    ("math.solve.symbolic", ("equation", "calculate", "math", "integral")),
    ("retrieval.synthesize.cited", ("document", "cite", "source", "find")),
    ("application.action.verified", ("edit", "file", "vscode", "open")),
)
_RISKS = (("rm -rf", "destructive.delete"), ("sudo", "privilege.escalation"), ("password", "secret.credential"), ("api key", "secret.api-key"), ("exfiltrate", "data.exfiltration"))
_COMPLEXITY = ("constraint", "verify", "without", "step", "multiple", "optimize", "concurrent", "security")
