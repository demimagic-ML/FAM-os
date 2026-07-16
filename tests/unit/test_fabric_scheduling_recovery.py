import unittest

from fam_os.fabric.recovery import FabricRecoveryPolicy, RemoteFailureKind
from fam_os.fabric.scheduling import FabricRouteCandidate, LatencyAwareFabricScheduler


class FabricSchedulingRecoveryTests(unittest.TestCase):
    def test_remote_wins_only_when_trusted_private_and_faster(self):
        local = FabricRouteCandidate("desktop", "small", True, 500, 0, True, True)
        remote = FabricRouteCandidate("server", "large", False, 100, 20, True, True)
        decision = LatencyAwareFabricScheduler().decide((local, remote))
        self.assertEqual("server", decision.selected_device_id)
        denied = FabricRouteCandidate("untrusted", "large", False, 1, 1, False, True)
        self.assertEqual("desktop", LatencyAwareFabricScheduler().decide((local, denied)).selected_device_id)

    def test_disconnect_and_partial_output_are_discarded_before_local_retry(self):
        policy = FabricRecoveryPolicy()
        for failure in (RemoteFailureKind.DISCONNECTED, RemoteFailureKind.PARTIAL_RESULT):
            decision = policy.decide(failure, True)
            self.assertTrue(decision.discard_remote_output)
            self.assertTrue(decision.retry_local)
            self.assertTrue(decision.preserve_acceptance)


if __name__ == "__main__":
    unittest.main()
