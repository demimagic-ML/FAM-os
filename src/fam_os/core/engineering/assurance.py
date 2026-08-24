"""Truthful assurance for engineering effects, independent of authority."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from fam_os.core.engineering._validation import aware, text, texts
from fam_os.core.engineering.version import ENGINEERING_CONTRACT_VERSION
from fam_os.core.engineering.results import EngineeringResultKind


class EngineeringExecutionAssurance(StrEnum):
    VERIFIED = "verified"
    EXECUTED_UNVERIFIED = "executed_unverified"
    VERIFICATION_WAIVED = "verification_waived"


@dataclass(frozen=True, slots=True)
class EngineeringExecutionRecord:
    record_id: str
    task_id: str
    grant_id: str
    effect_id: str
    recorded_at: datetime
    effect_applied: bool
    assurance: EngineeringExecutionAssurance
    verifier_run_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    waiver_decision_id: str | None = None
    result_kind: EngineeringResultKind = EngineeringResultKind.EXECUTION_RECORD
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in ("record_id", "task_id", "grant_id", "effect_id"):
            text(getattr(self, name), name)
        aware(self.recorded_at, "recorded_at")
        texts(self.verifier_run_ids, "verifier_run_ids")
        texts(self.evidence_ids, "evidence_ids")
        if not self.evidence_ids:
            raise ValueError("engineering execution record requires effect evidence")
        if self.assurance is EngineeringExecutionAssurance.VERIFIED:
            if not self.effect_applied or not self.verifier_run_ids:
                raise ValueError("verified engineering execution requires passing verifier evidence")
            if self.waiver_decision_id is not None:
                raise ValueError("verified engineering execution cannot carry a waiver")
        elif self.assurance is EngineeringExecutionAssurance.EXECUTED_UNVERIFIED:
            if not self.effect_applied or self.verifier_run_ids or self.waiver_decision_id is not None:
                raise ValueError("executed-unverified state cannot claim verifier or waiver evidence")
        elif self.assurance is EngineeringExecutionAssurance.VERIFICATION_WAIVED:
            if not self.effect_applied or self.verifier_run_ids or self.waiver_decision_id is None:
                raise ValueError("verification-waived state requires an explicit waiver decision")
            text(self.waiver_decision_id, "waiver_decision_id")
        if self.result_kind is not EngineeringResultKind.EXECUTION_RECORD:
            raise ValueError("engineering execution result kind is fixed")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("engineering execution record version is unsupported")


def classify_execution_assurance(
    *, verifier_passed: bool, waiver_decision_id: str | None,
) -> EngineeringExecutionAssurance:
    if verifier_passed:
        if waiver_decision_id is not None:
            raise ValueError("verified execution cannot also be verification-waived")
        return EngineeringExecutionAssurance.VERIFIED
    if waiver_decision_id is not None:
        text(waiver_decision_id, "waiver_decision_id")
        return EngineeringExecutionAssurance.VERIFICATION_WAIVED
    return EngineeringExecutionAssurance.EXECUTED_UNVERIFIED
