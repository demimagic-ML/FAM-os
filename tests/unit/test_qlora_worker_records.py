import json
import tempfile
import unittest
from pathlib import Path

from fam_os.adapters.training.qlora_worker import _load_config, _records


class QloraWorkerRecordTests(unittest.TestCase):
    def test_records_match_no_thinking_chat_inference_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "train.jsonl"
            path.write_text(
                json.dumps({"input": "Return only 421.", "completion": "421"})
                + "\n",
                encoding="utf-8",
            )

            self.assertEqual([
                {
                    "prompt": [{"role": "user", "content": "Return only 421."}],
                    "completion": [{"role": "assistant", "content": "421"}],
                    "chat_template_kwargs": {"enable_thinking": False},
                },
            ], _records(path))

    def test_config_rejects_the_legacy_raw_record_format(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "config.json"
            document = {
                "alpha": 32,
                "base_model_directory": "/model",
                "base_model_sha256": "a" * 64,
                "compute_dtype": "bfloat16",
                "dropout": 0.05,
                "epochs": 2.0,
                "gradient_accumulation_steps": 4,
                "learning_rate": 0.0002,
                "maximum_sequence_tokens": 1024,
                "maximum_steps": 1,
                "output_directory": "/output",
                "per_device_batch_size": 1,
                "rank": 16,
                "record_format": "raw_prompt_completion_v1",
                "seed": 42,
                "target_modules": ["all-linear"],
                "train_dataset": "/input/train.jsonl",
                "train_sha256": "b" * 64,
                "validation_dataset": "/input/validation.jsonl",
                "validation_sha256": "c" * 64,
            }
            path.write_text(json.dumps(document), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "record format"):
                _load_config(path)


if __name__ == "__main__":
    unittest.main()
