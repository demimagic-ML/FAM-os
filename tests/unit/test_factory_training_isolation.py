import tempfile
import unittest
from pathlib import Path

from fam_os.adapters.training.isolated_command import (
    IsolatedTrainingPaths,
    build_isolated_training_command,
)
from fam_os.adapters.training.nvidia_qlora_backend import (
    _directory_bytes,
    _directory_manifest_sha256,
    _file_sha256,
    _held_out_absent,
    _validate_completed_artifacts,
)
from tests.unit.test_factory_training_approval import _Dataset, _approval


class FactoryTrainingIsolationTests(unittest.TestCase):
    def test_worker_command_denies_network_and_binds_only_train_inputs(self):
        approval = _approval("proposal-1", _Dataset())
        command = build_isolated_training_command(
            job_id=approval.one_use_job_id, approval=approval,
            paths=IsolatedTrainingPaths(
                Path("/factory/environment"), Path("/factory/qlora_worker.py"),
                Path("/factory/model"), Path("/factory/jobs/job-1/input"),
                Path("/factory/jobs/job-1/output"),
            ),
        )
        joined = " ".join(command)
        self.assertIn("--unshare-all", command)
        self.assertNotIn("--share-net", command)
        self.assertIn("/bin", command)
        self.assertIn("/sbin", command)
        self.assertIn("HF_HUB_OFFLINE 1", joined)
        self.assertIn("TRANSFORMERS_OFFLINE 1", joined)
        self.assertIn("HF_HOME /tmp/huggingface", joined)
        self.assertIn("XDG_CACHE_HOME /tmp/cache", joined)
        self.assertIn("MemorySwapMax=0", command)
        self.assertIn(f"MemoryMax={approval.resources.maximum_ram_bytes}", command)
        self.assertIn("/input/config.json", command)
        self.assertNotIn("held_out", joined)

    def test_relative_or_unsafe_job_identity_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "absolute"):
            IsolatedTrainingPaths(
                Path("relative"), Path("/worker"), Path("/model"),
                Path("/input"), Path("/output"),
            )
        with self.assertRaisesRegex(ValueError, "unsafe"):
            build_isolated_training_command(
                job_id="bad/job", approval=_approval("proposal-1", _Dataset()),
                paths=IsolatedTrainingPaths(
                    Path("/environment"), Path("/worker"), Path("/model"),
                    Path("/input"), Path("/output"),
                ),
            )

    def test_parent_recomputes_completed_worker_artifacts_and_input_boundary(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "output"
            adapter = output / "adapter"
            input_directory = root / "input"
            adapter.mkdir(parents=True)
            input_directory.mkdir()
            (adapter / "adapter_config.json").write_text("{}\n", encoding="utf-8")
            (adapter / "adapter_model.safetensors").write_bytes(b"adapter")
            (output / "metrics.json").write_text("{}\n", encoding="utf-8")
            for name in ("config.json", "train.jsonl", "validation.jsonl"):
                (input_directory / name).write_text("{}\n", encoding="utf-8")
            worker = {
                "adapter_bytes": _directory_bytes(adapter),
                "adapter_config_sha256": _file_sha256(
                    adapter / "adapter_config.json",
                ),
                "adapter_sha256": _directory_manifest_sha256(adapter),
                "base_weights_frozen": True,
                "duration_seconds": 1.0,
                "metrics_sha256": _file_sha256(output / "metrics.json"),
                "reason_code": "training.completed", "status": "completed",
                "unexpected_trainable_parameters": [],
            }
            self.assertIsNone(_validate_completed_artifacts(output, worker))
            self.assertTrue(_held_out_absent(input_directory))
            (adapter / "adapter_model.safetensors").write_bytes(b"tampered")
            self.assertEqual(
                "training.adapter_digest_mismatch",
                _validate_completed_artifacts(output, worker),
            )
            (input_directory / "held_out.jsonl").write_text("{}\n", encoding="utf-8")
            self.assertFalse(_held_out_absent(input_directory))


if __name__ == "__main__":
    unittest.main()
