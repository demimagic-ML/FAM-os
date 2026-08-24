"""Translate completed adapted inference into content-free health evidence."""

from __future__ import annotations

import hashlib

from fam_os.adaptation import AdaptationHealthSample


def terminal_health_sample(observation, result, observed_at) -> AdaptationHealthSample:
    identity = (
        f"{observation.observation_id}\0{result.status.value}\0{int(result.verified)}"
    )
    reasons = [*observation.runtime_health.reason_codes]
    reasons.append(
        "acceptance.verified" if result.verified else "acceptance.not_verified"
    )
    return AdaptationHealthSample(
        f"adaptation-health-{hashlib.sha256(identity.encode('utf-8')).hexdigest()}",
        observation.observation_id,
        hashlib.sha256(observation.request_id.encode("utf-8")).hexdigest(),
        observation.snapshot_id,
        observation.workflow_id,
        observation.model_ref,
        observed_at,
        float(result.verified),
        max(observation.wall_seconds, .000001),
        observation.runtime_health.peak_temperature_c,
        observation.runtime_health.policy_conformant,
        tuple(dict.fromkeys(reasons)),
    )
