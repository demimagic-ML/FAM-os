"""Pure derivation of live advice from content-free verified learning."""

from __future__ import annotations

import hashlib
from datetime import datetime

from fam_os.adaptation import (
    LiveAdaptationSnapshot,
    LocalOutcomePredictor,
    VerifiedLearningOutcome,
    VerifiedOutcomeObservation,
)
from fam_os.core.production.contracts import ModelIntent
from fam_os.scheduler import ExpertUseObservation, LocalExpertFrequencyLearner
from fam_os.scheduler.cache_contracts import CacheTier
from fam_os.scheduler.prefetch_prediction import (
    ArtifactAccessSequence,
    PrefetchCandidate,
    PrefetchPredictionRequest,
)
from fam_os.scheduler.prefetch_predictor import DeterministicTransitionPredictor


def build_live_snapshot(
    workflow_id: str,
    records: tuple[VerifiedLearningOutcome, ...],
    catalog,
    created_at: datetime,
) -> LiveAdaptationSnapshot | None:
    values = tuple(item for item in records if item.workflow_id == workflow_id)
    if len(values) < 2:
        return None
    outcome = LocalOutcomePredictor().predict(
        _identity("outcome", workflow_id, values), workflow_id,
        _outcome_observations(values),
    )
    if outcome is None:
        return None
    frequencies = LocalExpertFrequencyLearner().learn(
        _identity("frequency", workflow_id, values), _frequency_observations(values),
    )
    intent = ModelIntent(workflow_id.removeprefix("intent:"))
    entries = catalog.for_intent(intent)
    allowed = {item.model_ref for item in entries}
    ordered = _frequency_order(frequencies.frequencies, allowed)
    transition = _transition(workflow_id, values, entries, created_at)
    source_digest = _source_digest(values)
    return LiveAdaptationSnapshot(
        _identity("snapshot", workflow_id, values), workflow_id, created_at,
        len(values), outcome.predicted_context_tokens,
        outcome.escalation_probability, outcome.prewarm_escalation, ordered,
        None if transition is None else transition.candidate.artifact_id,
        None if transition is None else transition.confidence,
        tuple(item.learning_id for item in values), source_digest,
    )


def _outcome_observations(values):
    return tuple(
        VerifiedOutcomeObservation(
            item.learning_id, item.workflow_id, item.observed_at, item.verified,
            item.context_token_bucket, item.escalation_used, item.evidence_sha256,
        )
        for item in values
    )


def _frequency_observations(values):
    return tuple(
        ExpertUseObservation(
            item.learning_id, item.expert_id, item.observed_at, item.verified,
        )
        for item in values
    )


def _frequency_order(frequencies, allowed):
    eligible = tuple(
        item for item in frequencies
        if item.expert_id in allowed and item.verified_uses >= 2
    )
    ranked = tuple(sorted(
        eligible,
        key=lambda item: (-item.verified_uses, -item.frequency, item.expert_id),
    ))
    if not ranked:
        return ()
    if len(ranked) > 1 and ranked[0].verified_uses == ranked[1].verified_uses:
        return ()
    return tuple(item.expert_id for item in ranked)


def _transition(workflow_id, values, entries, created_at):
    history = tuple(
        ArtifactAccessSequence(
            _pair_identity(left, right), right.observed_at,
            (left.expert_id, right.expert_id), _pair_digest(left, right),
        )
        for left, right in zip(values, values[1:])
    )
    if not history:
        return None
    candidates = tuple(
        PrefetchCandidate(
            item.model_ref, CacheTier.PROVIDER_WEIGHTS,
            item.estimated_resident_bytes, item.estimated_resident_bytes,
            max(1.0, item.estimated_resident_bytes / 100_000.0),
        )
        for item in entries
    )
    if not candidates:
        return None
    request = PrefetchPredictionRequest(
        _identity("transition-request", workflow_id, values), values[-1].expert_id,
        created_at, candidates, history, 2, 0.75, 600,
    )
    return DeterministicTransitionPredictor().predict(
        _identity("transition", workflow_id, values), request,
    )


def _identity(kind: str, workflow_id: str, values) -> str:
    source = "\0".join((kind, workflow_id, *(item.learning_id for item in values)))
    return f"live-{kind}-{hashlib.sha256(source.encode()).hexdigest()}"


def _pair_identity(left, right) -> str:
    source = f"{left.learning_id}\0{right.learning_id}".encode()
    return f"transition-sequence-{hashlib.sha256(source).hexdigest()}"


def _pair_digest(left, right) -> str:
    return hashlib.sha256(
        f"{left.evidence_sha256}\0{right.evidence_sha256}".encode(),
    ).hexdigest()


def _source_digest(values) -> str:
    source = "\0".join(
        f"{item.learning_id}:{item.evidence_sha256}" for item in values
    )
    return hashlib.sha256(source.encode()).hexdigest()
