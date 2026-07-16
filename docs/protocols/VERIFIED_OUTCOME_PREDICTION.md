# Verified outcome prediction

Phase 11.2 learns context and escalation predictions only from independently verified final outcomes. Each label retains a digest of its source evidence. Context uses a conservative observed 95th percentile; escalation probability is the observed verified escalation rate. Too few samples produce no prediction.

Predictions are local-only scheduling advice. They may reserve context or prewarm a strong tier, but they never weaken acceptance, skip verification, or force escalation.
