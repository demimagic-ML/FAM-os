import unittest
from dataclasses import replace

from fam_os.scheduler import (
    ContextMemoryEstimator,
    DeterministicGpuPlacementPolicy,
    GpuPlacementRequest,
    ResidentWeightEstimate,
    WeightEstimateSource,
)
from fam_os.scheduler.admission_contracts import AdmissionStatus
from fam_os.scheduler.context_contracts import (
    ContextMemoryModelProfile,
    ContextMemoryReservation,
    ContextMemoryStrategy,
    ContextProfileSource,
)
from fam_os.scheduler.live_contracts import ObservationStatus
from tests.contract.schema_scheduler_fixtures import live_resource_observation


def request(layers=14, observation=None):
    profile = ContextMemoryModelProfile(
        "context.model", "expert.model", "model:latest", "test",
        ContextMemoryStrategy.AUTOREGRESSIVE_KV, 4096, 28, 1024, 8,
        4, 128, 128, 2, 100, 100, 0,
        ContextProfileSource.DECLARED_CONSERVATIVE,
    )
    context = ContextMemoryEstimator().estimate(
        "estimate-1", profile, ContextMemoryReservation("reservation-1", profile.profile_id, 512, 64)
    )
    return GpuPlacementRequest(
        "request-1", "expert.model", observation or live_resource_observation(),
        ResidentWeightEstimate(
            "expert.model", "model:latest", 4_000_000,
            WeightEstimateSource.DECLARED_CONSERVATIVE, "test bound",
        ),
        context, "gpu-0", 28, layers, 0,
    )


class DeterministicGpuPlacementPolicyTests(unittest.TestCase):
    def setUp(self):
        self.policy = DeterministicGpuPlacementPolicy()

    def test_separates_host_and_accelerator_vectors(self):
        decision = self.policy.decide("decision-1", request())
        self.assertEqual(decision.status, AdmissionStatus.ADMITTED)
        self.assertEqual(decision.accelerator_weight_bytes, 2_000_000)
        self.assertEqual(decision.host_weight_compute_bytes, 2_000_000)
        self.assertEqual(decision.estimated_transfer_bytes, 2_000_000)
        self.assertGreater(decision.host_safety_reservation_bytes, 4_000_000)

    def test_rejects_accelerator_shortfall_without_spending_host_capacity(self):
        observation = live_resource_observation()
        gpu = replace(
            observation.accelerators[0], scheduler_limit_bytes=1,
            current_bytes=0, available_for_new_bytes=1,
        )
        decision = self.policy.decide(
            "decision-1", request(observation=replace(observation, accelerators=(gpu,)))
        )
        self.assertEqual(decision.status, AdmissionStatus.REJECTED)
        self.assertIn("accelerator_memory.insufficient", decision.reason_codes)

    def test_fails_closed_on_degraded_observation_even_when_vectors_fit(self):
        observation = replace(
            live_resource_observation(), status=ObservationStatus.DEGRADED,
            reason_codes=("test.telemetry_missing",),
        )
        decision = self.policy.decide("decision-1", request(observation=observation))
        self.assertEqual(decision.status, AdmissionStatus.REJECTED)
        self.assertEqual(decision.reason_codes, ("resource_observation.degraded",))

    def test_rejects_layer_count_above_model(self):
        with self.assertRaisesRegex(ValueError, "exceed"):
            request(29)


if __name__ == "__main__":
    unittest.main()
