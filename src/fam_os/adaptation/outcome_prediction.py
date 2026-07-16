"""Context and escalation predictions learned only from verified outcomes."""

from dataclasses import dataclass
from datetime import datetime

OUTCOME_PREDICTION_CONTRACT_VERSION = "fam.adaptation.outcome-prediction/v1alpha1"


@dataclass(frozen=True, slots=True)
class VerifiedOutcomeObservation:
    observation_id: str
    workflow_id: str
    observed_at: datetime
    verified: bool
    required_context_tokens: int
    escalation_used: bool
    evidence_sha256: str

    def __post_init__(self) -> None:
        if not self.verified:
            raise ValueError("adaptation outcomes must be independently verified")
        if self.observed_at.tzinfo is None or self.required_context_tokens <= 0:
            raise ValueError("verified outcome requires time and context")
        if len(self.evidence_sha256) != 64:
            raise ValueError("verified outcome requires SHA-256 evidence")


@dataclass(frozen=True, slots=True)
class WorkflowOutcomePrediction:
    prediction_id: str
    workflow_id: str
    observation_count: int
    predicted_context_tokens: int
    escalation_probability: float
    prewarm_escalation: bool
    source_observation_ids: tuple[str, ...]
    local_only: bool = True
    contract_version: str = OUTCOME_PREDICTION_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if not self.local_only or self.observation_count != len(self.source_observation_ids):
            raise ValueError("outcome prediction must retain local source observations")
        if not 0 <= self.escalation_probability <= 1:
            raise ValueError("escalation probability must be normalized")


class LocalOutcomePredictor:
    def predict(self, prediction_id, workflow_id, observations, minimum_samples=2,
                prewarm_threshold=.75):
        values = tuple(item for item in observations if item.workflow_id == workflow_id)
        if len(values) < minimum_samples:
            return None
        contexts = sorted(item.required_context_tokens for item in values)
        index = max(0, (95 * len(contexts) + 99) // 100 - 1)
        probability = sum(item.escalation_used for item in values) / len(values)
        return WorkflowOutcomePrediction(
            prediction_id, workflow_id, len(values), contexts[index], probability,
            probability >= prewarm_threshold,
            tuple(item.observation_id for item in values),
        )
