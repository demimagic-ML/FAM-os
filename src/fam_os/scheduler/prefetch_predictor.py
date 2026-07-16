"""Deterministic bounded transition predictor."""

from __future__ import annotations

from datetime import timedelta

from fam_os.scheduler.prefetch_prediction import (
    PrefetchPrediction,
    PrefetchPredictionRequest,
)


class DeterministicTransitionPredictor:
    def predict(self, prediction_id: str, request: PrefetchPredictionRequest):
        candidates = {item.artifact_id: item for item in request.candidates}
        counts = {artifact_id: 0 for artifact_id in candidates}
        sources = {artifact_id: [] for artifact_id in candidates}
        outgoing = 0
        for sequence in request.history:
            for current, following in zip(sequence.artifact_ids, sequence.artifact_ids[1:]):
                if current != request.current_artifact_id:
                    continue
                outgoing += 1
                if following in counts:
                    counts[following] += 1
                    sources[following].append(sequence.sequence_id)
        if outgoing == 0:
            return None
        selected = min(candidates, key=lambda item: (-counts[item], item))
        observations = counts[selected]
        confidence = observations / outgoing
        if observations < request.minimum_transition_observations:
            return None
        if confidence < request.minimum_confidence:
            return None
        return PrefetchPrediction(
            prediction_id, request.request_id, candidates[selected], observations,
            outgoing, confidence, request.requested_at,
            request.requested_at + timedelta(seconds=request.horizon_seconds),
            tuple(sources[selected]),
        )
