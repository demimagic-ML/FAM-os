import unittest

from fam_os.experts.evolution_policy import ExpertEvolutionPolicy, ExpertPerformanceSlice


def sample(expert, cluster, passed, energy=1):
    return ExpertPerformanceSlice(expert, "code.generate", cluster, passed, 20, energy)


class ExpertEvolutionPolicyTests(unittest.TestCase):
    def test_split_requires_sufficient_cluster_gap(self):
        proposal = ExpertEvolutionPolicy().split("general", (
            sample("general", "python", 19), sample("general", "rust", 10),
        ))
        self.assertEqual("split", proposal.action)
        self.assertFalse(proposal.state_mutated)

    def test_merge_requires_redundant_quality_across_shared_clusters(self):
        proposal = ExpertEvolutionPolicy().merge("a", "b", (
            sample("a", "python", 18), sample("b", "python", 18),
        ))
        self.assertEqual(("a", "b"), proposal.subject_expert_ids)

    def test_retirement_requires_quality_and_energy_dominance(self):
        policy = ExpertEvolutionPolicy()
        proposal = policy.retire("old", "new", (
            sample("old", "python", 14, .02), sample("new", "python", 18, .03),
        ))
        self.assertEqual("retire", proposal.action)
        blocked = policy.retire("old", "new", (
            sample("old", "python", 14, .04), sample("new", "python", 18, .03),
        ))
        self.assertIsNone(blocked)

    def test_small_samples_cannot_trigger_change(self):
        weak = ExpertPerformanceSlice("a", "code.generate", "python", 1, 2, 1)
        self.assertIsNone(ExpertEvolutionPolicy().split("a", (weak, weak)))


if __name__ == "__main__":
    unittest.main()
