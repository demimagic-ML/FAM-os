import json
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from fam_os.expert_factory import (
    DatasetPartition,
    build_sealed_dataset_blob_receipt,
    canonical_partition_bytes,
    seal_factory_dataset,
)
from fam_os.product.factory_training_workspace import (
    FactoryTrainingWorkspace,
    model_files_manifest_sha256,
)
from tests.unit.test_factory_dataset_sealing import _source
from tests.unit.test_factory_training_approval import _approval


NOW = datetime(2026, 7, 17, 23, tzinfo=UTC)


class FactoryTrainingWorkspaceTests(unittest.TestCase):
    def test_workspace_decrypts_train_and_validation_but_never_held_out(self):
        sources = tuple(
            _source(
                partition, f"source-{partition.value}",
                f"PRIVATE_{partition.value}_INPUT",
                f"PRIVATE_{partition.value}_OUTPUT",
            )
            for partition in DatasetPartition
        )
        dataset, report = seal_factory_dataset(
            dataset_id="sealed-workspace-dataset", proposal_id="proposal-1",
            capability_id="intent.code", sources=sources,
            examples=(), reviews=(), sealed_at=NOW,
        )
        self.assertTrue(report.passed)
        assert dataset is not None
        payloads = {
            item.partition: canonical_partition_bytes(item, sources, (), ())
            for item in dataset.partitions
        }
        blobs = tuple(
            build_sealed_dataset_blob_receipt(
                blob_id=item.blob_id, dataset_id=dataset.dataset_id,
                partition=item.partition,
                plaintext_sha256=item.ordered_records_sha256,
                ciphertext_sha256="a" * 64,
                plaintext_bytes=len(payloads[item.partition]),
                ciphertext_bytes=len(payloads[item.partition]) + 100,
                relative_path=f"blobs/aa/{item.blob_id}.blob", created_at=NOW,
            )
            for item in dataset.partitions
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            model = root / "model"
            model.mkdir()
            (model / "config.json").write_text("{}\n", encoding="utf-8")
            model_sha256 = model_files_manifest_sha256(model)
            approval = _approval("proposal-1", dataset)
            approval = replace(
                approval,
                base_model=replace(
                    approval.base_model, files_manifest_sha256=model_sha256,
                ),
            )
            workspace = FactoryTrainingWorkspace(
                root / "jobs", _BlobStore(payloads), root.stat().st_uid,
            ).prepare(
                approval=approval, dataset=dataset, blobs=blobs,
                model_directory=model,
            )
            combined = "\n".join(
                item.read_text("utf-8") for item in workspace.input_directory.iterdir()
            )
            self.assertIn("PRIVATE_train_INPUT", combined)
            self.assertIn("PRIVATE_validation_INPUT", combined)
            self.assertNotIn("PRIVATE_held_out_INPUT", combined)
            self.assertEqual(0o600, workspace.train_path.stat().st_mode & 0o777)
            config_text = workspace.config_path.read_text("utf-8")
            self.assertNotIn(str(model), config_text)
            self.assertEqual(
                "qwen_chat_prompt_completion_v1",
                json.loads(config_text)["record_format"],
            )


class _BlobStore:
    def __init__(self, payloads):
        self._payloads = payloads

    def read(self, receipt):
        return self._payloads[receipt.partition]


if __name__ == "__main__":
    unittest.main()
