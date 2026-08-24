import os
import tempfile
import unittest
from pathlib import Path

from fam_os.product.factory_evaluation_workspace import FactoryEvaluationWorkspace
from fam_os.product.factory_evaluations import ProductFactoryEvaluationApprovals
from tests.unit.test_factory_evaluation import NOW, _policy
from tests.unit.test_factory_evaluation_repository import _completed_training
from tests.unit.test_factory_training_approval import _repositories


class _BlobReader:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def read(self, _receipt) -> bytes:
        return self.payload


class FactoryEvaluationProductTests(unittest.TestCase):
    def test_approval_derives_exact_immutable_training_and_held_out_lineage(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database, repositories, proposal_id, dataset = _repositories(root)
            training, terminal = _completed_training(
                repositories, proposal_id, dataset,
            )
            service = ProductFactoryEvaluationApprovals(
                repositories, now=lambda: NOW,
            )
            with self.assertRaisesRegex(PermissionError, "confirmation"):
                service.issue(**_issue_values(terminal, confirmed=False))
            approval = service.issue(**_issue_values(terminal, confirmed=True))
            self.assertEqual(terminal.adapter_sha256, approval.adapter_sha256)
            self.assertEqual(dataset.manifest_sha256, approval.sealed_dataset_sha256)
            self.assertEqual(training.capability_id, approval.policy.capability_id)
            database.close()

    def test_held_out_plaintext_exists_only_inside_evaluator_context(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database, repositories, proposal_id, dataset = _repositories(root)
            _, terminal = _completed_training(repositories, proposal_id, dataset)
            approval = ProductFactoryEvaluationApprovals(
                repositories, now=lambda: NOW,
            ).issue(**_issue_values(terminal, confirmed=True))
            held_out = next(
                item for item in repositories.sealed_datasets.blobs(dataset.dataset_id)
                if item.partition.value == "held_out"
            )
            payload = b'{"input":"secret","completion":"answer"}\n'
            held_out = _matching_receipt(held_out, payload)
            approval = _matching_approval(approval, held_out.plaintext_sha256)
            workspace_root = root / "evaluation-workspaces"
            workspace = FactoryEvaluationWorkspace(
                workspace_root, _BlobReader(payload), os.geteuid(),
            )
            with workspace.materialize(
                approval=approval, held_out=held_out,
            ) as prepared:
                self.assertEqual(payload, prepared.held_out_path.read_bytes())
                self.assertNotIn("training-job", str(prepared.root))
            self.assertFalse(prepared.root.exists())
            self.assertFalse(any(workspace_root.rglob("held-out.jsonl")))
            database.close()


def _issue_values(terminal, *, confirmed: bool):
    return {
        "request_id": "evaluation-request-1",
        "training_receipt_id": terminal.receipt_id,
        "incumbent_expert_id": "qwen3-1.7b-base",
        "incumbent_artifact_sha256": "d" * 64,
        "suite_sha256": "e" * 64,
        "evaluator_environment_sha256": terminal.environment_sha256,
        "evaluator_script_sha256": "f" * 64,
        "policy": _policy(), "one_use_evaluation_id": "evaluation-product-1",
        "lifetime_seconds": 3600, "confirmed": confirmed,
    }


def _matching_receipt(receipt, payload: bytes):
    from dataclasses import replace
    import hashlib

    digest = hashlib.sha256(payload).hexdigest()
    return replace(receipt, plaintext_sha256=digest, plaintext_bytes=len(payload),
                   receipt_sha256=_blob_receipt_digest(receipt, digest, len(payload)))


def _blob_receipt_digest(receipt, digest: str, size: int) -> str:
    from fam_os.expert_factory import build_sealed_dataset_blob_receipt

    rebuilt = build_sealed_dataset_blob_receipt(
        blob_id=receipt.blob_id, dataset_id=receipt.dataset_id,
        partition=receipt.partition, plaintext_sha256=digest,
        ciphertext_sha256=receipt.ciphertext_sha256, plaintext_bytes=size,
        ciphertext_bytes=receipt.ciphertext_bytes,
        relative_path=receipt.relative_path, created_at=receipt.created_at,
    )
    return rebuilt.receipt_sha256


def _matching_approval(approval, digest: str):
    from fam_os.expert_factory import build_evaluation_approval

    values = {
        name: getattr(approval, name) for name in approval.__dataclass_fields__
        if name not in {"held_out_blob_sha256", "approval_sha256", "contract_version"}
    }
    return build_evaluation_approval(**values, held_out_blob_sha256=digest)


if __name__ == "__main__":
    unittest.main()
