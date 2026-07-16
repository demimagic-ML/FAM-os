import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from fam_os.expert_factory.objective import HardwareObjectiveWeights, HardwareTrainingMetrics, hardware_objective
from fam_os.expert_factory.quantization import QuantizedVariant
from fam_os.expert_factory.regression import evaluate_regression
from fam_os.expert_factory.release import sign_and_publish, verify_published
from fam_os.expert_factory.training import LabeledExample, train_micro_expert


class ExpertFactoryPipelineTests(unittest.TestCase):
    def test_routing_and_complexity_models_are_actually_trained(self):
        routing = train_micro_expert("routing", "routing.classify", "fam.micro/v1", (
            LabeledExample("write python function", "code"),
            LabeledExample("summarize this document", "language"),
        ))
        complexity = train_micro_expert("complexity", "routing.complexity", "fam.micro/v1", (
            LabeledExample("short easy answer", "low"), LabeledExample("complex proof algorithm", "high"),
        ))
        self.assertEqual("code", routing.predict("python code"))
        self.assertEqual("high", complexity.predict("complex algorithm"))

    def test_hardware_objective_quantization_release_and_gate(self):
        score = hardware_objective(HardwareTrainingMetrics(.95, 100, 200, .1, 2),
                                   HardwareObjectiveWeights(.0001, .00001, .1, .01))
        self.assertLess(score, .95)
        variant = QuantizedVariant("q4", "expert", "int4", 4, "a" * 64, 100,
                                   "b" * 64, .98, .03, True)
        self.assertTrue(variant.passed)
        gate = evaluate_regression("gate", .9, .95, 1, .5, 10, 5, True)
        self.assertTrue(gate.passed)
        with tempfile.TemporaryDirectory() as directory:
            key = Ed25519PrivateKey.generate()
            package = sign_and_publish("expert", {"variant": "q4"}, "key", key, Path(directory))
            self.assertEqual({"variant": "q4"}, verify_published(Path(package.publication_path), key.public_key()))


if __name__ == "__main__":
    unittest.main()
