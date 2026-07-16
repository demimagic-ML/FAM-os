"""Evidence that small-tier failure escalated without weakening acceptance."""

from dataclasses import dataclass

ESCALATION_TRACE_CONTRACT_VERSION = "fam.expert.escalation-trace/v1alpha1"


@dataclass(frozen=True, slots=True)
class EscalationBudgetEvidence:
    consumed_tokens: int
    consumed_wall_milliseconds: int
    repairs: int
    escalations: int
    reservation_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EscalationTraceReport:
    trace_id: str
    economical_model_ref: str
    escalation_model_ref: str
    escalation_expert_id: str
    package_artifact_sha256: str
    attempt_kinds: tuple[str, ...]
    verification_statuses: tuple[str, ...]
    acceptance_id: str
    trusted_tests_sha256: str
    repair_examples_sha256: str
    maximum_failure_feedback_characters: int
    global_budget: EscalationBudgetEvidence
    verified: bool
    raw_report_sha256: str
    contract_version: str = ESCALATION_TRACE_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.economical_model_ref == self.escalation_model_ref:
            raise ValueError("escalation trace requires distinct model tiers")
        if not self.attempt_kinds or self.attempt_kinds[0] != "economical":
            raise ValueError("escalation trace must begin at economical tier")
        if "escalation" not in self.attempt_kinds:
            raise ValueError("escalation trace must contain escalation")
        if self.verification_statuses[0] != "failed":
            raise ValueError("escalation trace requires a small-tier failure")
        if self.verified != (self.verification_statuses[-1] == "passed"):
            raise ValueError("escalation verification must match final attempt")
        for value in (
            self.package_artifact_sha256, self.trusted_tests_sha256,
            self.repair_examples_sha256, self.raw_report_sha256,
        ):
            if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
                raise ValueError("escalation evidence digests must be lowercase SHA-256")
        if not 0 < self.maximum_failure_feedback_characters <= 4000:
            raise ValueError("failure feedback must be bounded to at most 4000 characters")
