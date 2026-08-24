import hashlib
import json
import stat
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from fam_os.adapters.training.evaluation_python_verifier import verify_document
from fam_os.expert_factory import DatasetPartition, SealedDatasetPartition
from tools.phase22_specialist_exit.evidence import _partition_evidence
from tools.phase22_specialist_exit.fixtures import (
    REFERENCE_SOLUTION,
    dataset_fixtures,
    evaluation_fixtures,
    evaluation_suite_bytes,
)
from tools.phase22_specialist_exit.sample_plans import (
    BALANCED1000,
    BALANCED2500,
    BALANCED5000,
    BALANCED512,
    DIVERSE2500,
    QUALITY256,
    sample_plan,
)
from tools.phase22_specialist_exit.training import _recipe
from tools.phase22_specialist_exit.private_output import write_private_json_new
from tools.phase22_specialist_exit.suite import (
    load_sealed_evaluation_suite,
    seal_evaluation_suite,
)


class Phase22SpecialistExitTests(unittest.TestCase):
    def test_checkpoint_evidence_writer_is_private_and_create_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "evidence.json"
            write_private_json_new(path, {"passed": False})
            self.assertEqual(0o600, stat.S_IMODE(path.stat().st_mode))
            self.assertEqual({"passed": False}, json.loads(path.read_text()))
            with self.assertRaises(FileExistsError):
                write_private_json_new(path, {"passed": True})

    def test_dataset_checkpoint_has_exact_split_before_capture_quotas(self) -> None:
        fixtures = dataset_fixtures()
        counts = Counter(
            (fixture.kind, fixture.partition.value) for fixture in fixtures
        )
        self.assertEqual(380, len(fixtures))
        self.assertEqual(380, len({item.source_id for item in fixtures}))
        self.assertEqual(380, len({item.source_family_id for item in fixtures}))
        self.assertEqual({
            ("quality", "train"): 256,
            ("quality", "validation"): 32,
            ("quality", "held_out"): 32,
            ("safety", "train"): 16,
            ("safety", "validation"): 2,
            ("safety", "held_out"): 2,
            ("policy", "train"): 16,
            ("policy", "validation"): 2,
            ("policy", "held_out"): 2,
            ("unrelated", "train"): 16,
            ("unrelated", "validation"): 2,
            ("unrelated", "held_out"): 2,
        }, dict(counts))

    def test_balanced_checkpoint_has_exact_512_training_examples(self) -> None:
        fixtures = dataset_fixtures(BALANCED512.plan_id)
        counts = Counter(
            (fixture.kind, fixture.partition.value) for fixture in fixtures
        )
        self.assertEqual(632, len(fixtures))
        self.assertEqual(632, len({item.source_id for item in fixtures}))
        self.assertEqual(632, len({item.source_family_id for item in fixtures}))
        self.assertEqual(512, sum(
            count for (kind, partition), count in counts.items()
            if partition == "train"
        ))
        self.assertEqual({
            ("quality", "train"): 256,
            ("quality", "validation"): 32,
            ("quality", "held_out"): 32,
            ("safety", "train"): 96,
            ("safety", "validation"): 12,
            ("safety", "held_out"): 8,
            ("policy", "train"): 96,
            ("policy", "validation"): 12,
            ("policy", "held_out"): 8,
            ("unrelated", "train"): 64,
            ("unrelated", "validation"): 8,
            ("unrelated", "held_out"): 8,
        }, dict(counts))
        self.assertEqual(512, sample_plan(BALANCED512.plan_id).training_examples)
        self.assertEqual(632, sample_plan(BALANCED512.plan_id).total_examples)

    def test_training_steps_are_derived_from_sealed_train_count(self) -> None:
        quality_recipe = _recipe(QUALITY256.plan_id, 304)
        balanced_recipe = _recipe(BALANCED512.plan_id, 512)
        self.assertEqual(152, quality_recipe.maximum_steps)
        self.assertEqual(256, balanced_recipe.maximum_steps)
        self.assertIn("-304-", quality_recipe.recipe_id)
        self.assertIn("-512-", balanced_recipe.recipe_id)

    def test_balanced_1000_checkpoint_has_fixed_held_out_floor(self) -> None:
        fixtures = dataset_fixtures(BALANCED1000.plan_id)
        counts = Counter(
            (fixture.kind, fixture.partition.value) for fixture in fixtures
        )
        self.assertEqual(1181, len(fixtures))
        self.assertEqual(1000, sum(
            count for (_kind, partition), count in counts.items()
            if partition == "train"
        ))
        self.assertEqual(125, sum(
            count for (_kind, partition), count in counts.items()
            if partition == "validation"
        ))
        self.assertEqual(56, sum(
            count for (_kind, partition), count in counts.items()
            if partition == "held_out"
        ))
        self.assertEqual(500, _recipe("balanced1000", 1000).maximum_steps)

    def test_balanced_2500_checkpoint_restores_quality_majority(self) -> None:
        fixtures = dataset_fixtures(BALANCED2500.plan_id)
        counts = Counter(
            (fixture.kind, fixture.partition.value) for fixture in fixtures
        )
        self.assertEqual(2868, len(fixtures))
        self.assertEqual(2500, sum(
            count for (_kind, partition), count in counts.items()
            if partition == "train"
        ))
        self.assertEqual(312, sum(
            count for (_kind, partition), count in counts.items()
            if partition == "validation"
        ))
        self.assertEqual(56, sum(
            count for (_kind, partition), count in counts.items()
            if partition == "held_out"
        ))
        self.assertEqual(1250, counts[("quality", "train")])
        self.assertEqual(500, counts[("policy", "train")])
        self.assertEqual(375, counts[("safety", "train")])
        self.assertEqual(375, counts[("unrelated", "train")])
        self.assertEqual(1250, _recipe("balanced2500", 2500).maximum_steps)

    def test_balanced_5000_checkpoint_increases_guardrail_coverage(self) -> None:
        fixtures = dataset_fixtures(BALANCED5000.plan_id)
        counts = Counter(
            (fixture.kind, fixture.partition.value) for fixture in fixtures
        )
        self.assertEqual(5681, len(fixtures))
        self.assertEqual(5000, sum(
            count for (_kind, partition), count in counts.items()
            if partition == "train"
        ))
        self.assertEqual(625, sum(
            count for (_kind, partition), count in counts.items()
            if partition == "validation"
        ))
        self.assertEqual(56, sum(
            count for (_kind, partition), count in counts.items()
            if partition == "held_out"
        ))
        self.assertEqual(2500, counts[("quality", "train")])
        self.assertEqual(1000, counts[("safety", "train")])
        self.assertEqual(1000, counts[("policy", "train")])
        self.assertEqual(500, counts[("unrelated", "train")])
        self.assertEqual(2500, _recipe("balanced5000", 5000).maximum_steps)

    def test_guardrail_training_is_diverse_but_held_out_stays_fixed(self) -> None:
        fixtures = dataset_fixtures(BALANCED5000.plan_id)
        safety_train = tuple(
            item for item in fixtures
            if item.kind == "safety" and item.partition is DatasetPartition.TRAIN
        )
        policy_train = tuple(
            item for item in fixtures
            if item.kind == "policy" and item.partition is DatasetPartition.TRAIN
        )
        safety_held = tuple(
            item for item in fixtures
            if item.kind == "safety" and item.partition is DatasetPartition.HELD_OUT
        )
        policy_held = tuple(
            item for item in fixtures
            if item.kind == "policy" and item.partition is DatasetPartition.HELD_OUT
        )
        self.assertGreaterEqual(len({item.completion for item in safety_train}), 8)
        self.assertGreaterEqual(len({item.completion for item in policy_train}), 8)
        self.assertGreaterEqual(len({item.input_text.split(": ", 1)[1] for item in safety_train}), 100)
        self.assertGreaterEqual(len({item.input_text.split(": ", 1)[1] for item in policy_train}), 100)
        self.assertEqual(1, len({item.completion for item in safety_held}))
        self.assertEqual(1, len({item.completion for item in policy_held}))
        self.assertTrue(all(item.input_text.startswith("Safety case ") for item in safety_held))
        self.assertTrue(all(item.input_text.startswith("Policy case ") for item in policy_held))

    def test_diverse_2500_plan_binds_new_guardrail_mixture(self) -> None:
        fixtures = dataset_fixtures(DIVERSE2500.plan_id)
        counts = Counter(
            (fixture.kind, fixture.partition.value) for fixture in fixtures
        )
        self.assertEqual(2868, len(fixtures))
        self.assertEqual(1250, counts[("quality", "train")])
        self.assertEqual(500, counts[("safety", "train")])
        self.assertEqual(500, counts[("policy", "train")])
        self.assertEqual(250, counts[("unrelated", "train")])
        self.assertEqual(312, sum(
            count for (_kind, partition), count in counts.items()
            if partition == "validation"
        ))
        self.assertEqual(56, sum(
            count for (_kind, partition), count in counts.items()
            if partition == "held_out"
        ))
        self.assertEqual(1250, _recipe("diverse2500", 2500).maximum_steps)

    def test_evaluator_suite_is_fixed_and_reference_solution_passes(self) -> None:
        fixtures = evaluation_fixtures()
        quality = tuple(item for item in fixtures if item.verifier == "python_tests")
        self.assertEqual(52, len(fixtures))
        self.assertEqual(52, len({item.case_id for item in fixtures}))
        self.assertEqual(40, len(quality))
        self.assertEqual(
            "21773b83ded29b5e0ac5aed3220db140f5fae216f2fcca976e3d1450ac1d2684",
            hashlib.sha256(evaluation_suite_bytes()).hexdigest(),
        )
        for fixture in quality:
            self.assertIsNotNone(fixture.test_source)
            self.assertTrue(verify_document({
                "candidate": REFERENCE_SOLUTION,
                "tests": fixture.test_source,
            }))

    def test_suite_is_owner_private_sealed_once_and_content_matches(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "sealed"
            sealed = seal_evaluation_suite(root)
            self.assertEqual(52, sealed.case_count)
            self.assertEqual(0o600, stat.S_IMODE(sealed.path.stat().st_mode))
            self.assertEqual(evaluation_suite_bytes(), sealed.path.read_bytes())
            documents = tuple(
                json.loads(line) for line in sealed.path.read_text().splitlines()
            )
            self.assertEqual(52, len(documents))
            self.assertEqual(sealed, load_sealed_evaluation_suite(root))
            with self.assertRaises(FileExistsError):
                seal_evaluation_suite(root)

    def test_partition_evidence_uses_the_contract_digest_field(self) -> None:
        partition = SealedDatasetPartition(
            DatasetPartition.TRAIN, "blob-1", ("record-1",), 1, 17, "a" * 64,
        )
        self.assertEqual({
            "blob_id": "blob-1",
            "ordered_records_sha256": "a" * 64,
            "content_bytes": 17,
            "record_count": 1,
        }, _partition_evidence(partition))


if __name__ == "__main__":
    unittest.main()
