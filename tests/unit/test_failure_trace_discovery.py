import unittest

from fam_os.expert_factory import FailureTrace, cluster_failures


class FailureTraceDiscoveryTests(unittest.TestCase):
    def test_repeated_verified_requirement_gap_proposes_capability(self):
        traces = tuple(FailureTrace(str(i), "code.stable-order", "input-order", "python", f"{i:x}" * 64,
                                    True) for i in (10, 11))
        clusters, proposals = cluster_failures(traces)
        self.assertEqual(2, proposals[0].observation_count)
        self.assertFalse(proposals[0].training_authorized)
        self.assertEqual(("10", "11"), clusters[0].trace_ids)

    def test_unverified_trace_is_rejected(self):
        with self.assertRaises(ValueError):
            FailureTrace("bad", "code.x", "r", "v", "a" * 64, False)


if __name__ == "__main__":
    unittest.main()
