import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from fam_os.adapters.sqlite import SQLiteEngineeringReviewStore
from fam_os.core.engineering import (
    EngineeringReviewResolutionReceipt, EngineeringReviewSelectionPolicy,
    EngineeringReviewService, EngineeringTaskDefinition,
    EngineeringReviewStatus, candidate_preview_digest,
    engineering_task_digest,
)
from fam_os.product.engineering_review_api import ProductEngineeringReviewApi
from tests.contract.schema_candidate_changeset_fixtures import (
    candidate_changeset_schema_values,
)
from tests.contract.schema_review_fixtures import review_schema_values
from tests.contract.schema_task_definition_fixtures import (
    task_definition_schema_values,
)
from tests.contract.schema_candidate_edit_fixtures import candidate_edit_schema_values
from tests.contract.schema_candidate_verification_fixtures import (
    candidate_verification_schema_values,
)


class ProductEngineeringReviewApiTests(unittest.TestCase):
    def test_exact_trusted_checkpoint_blocks_until_trusted_resolution_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            changeset = candidate_changeset_schema_values()[0]
            checkpoint = replace(
                review_schema_values()[0], task_id=changeset.task_id,
                candidate_id=changeset.candidate_id,
                changeset_sha256=candidate_preview_digest(changeset.preview),
            )
            service = EngineeringReviewService(SQLiteEngineeringReviewStore(
                Path(temporary) / "reviews.sqlite3",
            ))
            task = _security_task()
            api = ProductEngineeringReviewApi(
                "owner-1", _Tasks(task), _Preparations(changeset),
                _Candidates(changeset), service,
            )
            selection = EngineeringReviewSelectionPolicy().select(task, changeset)
            checkpoint = replace(
                checkpoint,
                required_disciplines=selection.required_disciplines,
            )
            api.record_selection("owner-1", selection)
            self.assertEqual(
                checkpoint, api.record_trusted("owner-1", checkpoint),
            )
            with self.assertRaisesRegex(PermissionError, "review is blocking"):
                api.require_passage("owner-1", changeset.task_id, changeset)
            edit = candidate_edit_schema_values()[0]
            verification = candidate_verification_schema_values()[0]
            api.record_trusted_resolution(
                "owner-1", EngineeringReviewResolutionReceipt(
                    "trusted-remediation-receipt-1", changeset.task_id,
                    changeset.candidate_id, candidate_preview_digest(changeset.preview),
                    checkpoint.checkpoint_id, checkpoint.findings[0].finding_id,
                    (edit.edit_id,), (verification.evidence.evidence_id,),
                    checkpoint.reviewer_id, checkpoint.reviewer_independence_ref,
                    checkpoint.completed_at,
                ),
            )
            passed = api.require_passage(
                "owner-1", changeset.task_id, changeset,
            )
            self.assertEqual("passed", passed[0].status.value)
            api.close()

    def test_checkpoint_for_another_candidate_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            changeset = candidate_changeset_schema_values()[0]
            checkpoint = replace(
                review_schema_values()[0], task_id=changeset.task_id,
                candidate_id="candidate-other",
                changeset_sha256=candidate_preview_digest(changeset.preview),
            )
            api = ProductEngineeringReviewApi(
                "owner-1", _Tasks(_security_task()), _Preparations(changeset),
                _Candidates(changeset),
                EngineeringReviewService(SQLiteEngineeringReviewStore(
                    Path(temporary) / "reviews.sqlite3",
                )),
            )
            with self.assertRaises(PermissionError):
                api.record_trusted("owner-1", checkpoint)
            api.close()


class _Tasks:
    def __init__(self, value):
        self.value = value

    def load(self, task_id):
        return self.value


class _Preparations:
    def __init__(self, changeset):
        self.value = SimpleNamespace(
            candidate=SimpleNamespace(candidate_id=changeset.candidate_id),
        )

    def load(self, task_id):
        return self.value


class _Candidates:
    def __init__(self, changeset):
        self.value = changeset

    def changesets(self, owner_id, task_id):
        return (self.value,)

    def edits(self, owner_id, task_id):
        return (candidate_edit_schema_values()[0],)

    def verifications(self, owner_id, task_id):
        return (candidate_verification_schema_values()[0],)


def _security_task():
    value = task_definition_schema_values()[0]
    task = replace(value.task, intent="Fix the security authentication boundary")
    return replace(value, task=task, task_sha256=engineering_task_digest(task))


if __name__ == "__main__":
    unittest.main()
