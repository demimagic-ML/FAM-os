import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from fam_os.adapters.sqlite import SQLiteEngineeringLoopStore
from fam_os.core.engineering import (
    CandidateApplyReceipt,
    CandidateApplyStatus,
    CandidateEntryKind,
    CandidateBaselineEntry,
    CandidatePreviewItem,
    CandidateOperationKind,
    CandidateTransactionPreview,
    CandidateWorkspace,
    CheckpointDecision,
    CheckpointDisposition,
    EngineeringEvidence,
    EngineeringLifecycleDriver,
    EngineeringLoopBudget,
    EngineeringLoopStage,
    EngineeringOutcome,
    GitLocalAction,
    GitLocalActionKind,
    GitLocalActionReceipt,
    GitPublicationApproval,
    GitPublicationKind,
    GitPublicationReceipt,
    MasterEngineeringLoop,
)
from tests.contract.schema_repository_fixtures import repository_schema_values, NOW


class EngineeringLifecycleDriverTests(unittest.TestCase):
    def test_typed_receipts_drive_complete_apply_commit_and_publication_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = SQLiteEngineeringLoopStore(Path(temporary) / "loop.sqlite3")
            loop = MasterEngineeringLoop(store)
            task_id = "task-repository-1"
            loop.start(
                task_id, "grant-1",
                EngineeringLoopBudget(1000, 1000, 100, 1000, 100, 10000),
                instant=NOW,
            )
            driver = EngineeringLifecycleDriver(loop, _allow_grant)
            _bundle, _request, analysis, proposal, _graph, _event = repository_schema_values()
            driver.record_inspection(analysis)
            driver.record_architecture(proposal)
            candidate = _candidate(task_id)
            driver.record_candidate(candidate)
            verified = _evidence(task_id, "verification-1")
            driver.record_verification(
                verified,
                additional_budget={"used_tokens": 20, "used_wall_seconds": 2},
            )
            driver.record_verification(_evidence(task_id, "verification-extra"))
            driver.record_verification(_evidence(task_id, "verification-extra"))
            self.assertEqual(
                ("verification-1", "verification-extra"),
                loop.state(task_id).verification_receipt_ids,
            )
            self.assertEqual(20, loop.state(task_id).budget.used_tokens)
            preview = _preview(candidate)
            driver.request_changeset_checkpoint(task_id, preview)
            driver.record_apply(task_id, _apply(candidate), _decision(task_id, preview))
            driver.record_reverification(_evidence(task_id, "verification-2"))
            driver.record_reverification(_evidence(task_id, "verification-3"))
            driver.record_reverification(_evidence(task_id, "verification-3"))
            self.assertEqual(
                (
                    "verification-1", "verification-extra",
                    "verification-2", "verification-3",
                ),
                loop.state(task_id).verification_receipt_ids,
            )
            action, commit = _commit(task_id)
            driver.record_commit(task_id, action, commit)
            approval, publication = _publication(task_id)
            driver.request_publication(approval)
            driver.record_publication(task_id, publication)
            driver.complete(_evidence(task_id, "completion-1"))
            state = loop.state(task_id)
            self.assertEqual(EngineeringLoopStage.COMPLETED, state.stage)
            self.assertEqual((commit.receipt_id,), state.git_receipt_ids)
            self.assertEqual((publication.receipt_id,), state.publication_receipt_ids)
            store.close()

    def test_claimed_or_mismatched_receipts_cannot_advance(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = SQLiteEngineeringLoopStore(Path(temporary) / "loop.sqlite3")
            loop = MasterEngineeringLoop(store)
            loop.start(
                "task-repository-1", "grant-1",
                EngineeringLoopBudget(100, 100, 10, 100, 10, 100), instant=NOW,
            )
            driver = EngineeringLifecycleDriver(loop, _allow_grant)
            _bundle, _request, analysis, proposal, _graph, _event = repository_schema_values()
            driver.record_inspection(analysis)
            driver.record_architecture(proposal)
            candidate = _candidate("task-repository-1")
            driver.record_candidate(candidate)
            with self.assertRaises(ValueError):
                driver.record_verification(EngineeringEvidence(
                    "failed-1", candidate.task_id, NOW, EngineeringOutcome.FAILED,
                    (), (), (), (), (), (), (), ("tests_failed",),
                ))
            self.assertEqual(EngineeringLoopStage.CANDIDATE_READY, loop.state(candidate.task_id).stage)
            store.close()

    def test_committed_rollback_requires_and_binds_inverse_git_commit(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = SQLiteEngineeringLoopStore(Path(temporary) / "loop.sqlite3")
            loop = MasterEngineeringLoop(store)
            task_id = "task-repository-1"
            loop.start(
                task_id, "grant-1",
                EngineeringLoopBudget(1000, 1000, 100, 1000, 100, 10000),
                instant=NOW,
            )
            driver = EngineeringLifecycleDriver(loop, _allow_grant)
            _bundle, _request, analysis, proposal, _graph, _event = repository_schema_values()
            driver.record_inspection(analysis)
            driver.record_architecture(proposal)
            candidate = _candidate(task_id)
            driver.record_candidate(candidate)
            driver.record_verification(_evidence(task_id, "verification-1"))
            preview = _preview(candidate)
            driver.request_changeset_checkpoint(task_id, preview)
            driver.record_apply(task_id, _apply(candidate), _decision(task_id, preview))
            driver.record_reverification(_evidence(task_id, "verification-2"))
            action, commit = _commit(task_id)
            driver.record_commit(task_id, action, commit)
            rollback = CandidateApplyReceipt(
                "transaction-1", candidate.candidate_id, NOW,
                CandidateApplyStatus.ROLLED_BACK, (), (), "9" * 64,
                True, "explicit rollback completed",
            )
            with self.assertRaisesRegex(ValueError, "inverse Git commit"):
                driver.record_rollback(task_id, rollback)
            inverse_action = GitLocalAction(
                "rollback-action-1", task_id, "/workspace",
                GitLocalActionKind.COMMIT, None, (), "Rollback change",
                "rollback-transaction-1", ("rollback-verification",),
                commit.after_object_id, NOW,
            )
            inverse_receipt = GitLocalActionReceipt(
                "rollback-git-receipt-1", inverse_action.action_id,
                commit.after_object_id, "3" * 40, (), "8" * 64, NOW,
            )
            driver.record_rollback(
                task_id, rollback, inverse_action, inverse_receipt,
            )
            state = loop.state(task_id)
            self.assertEqual(EngineeringLoopStage.ROLLED_BACK, state.stage)
            self.assertIn(
                inverse_receipt.receipt_id, state.rollback_receipt_ids[0],
            )
            store.close()


def _candidate(task_id):
    return CandidateWorkspace(
        "candidate-1", task_id, "baseline-1", "/workspace",
        "/transactions/candidate-1/workspace", NOW, "copy", "a" * 64,
        (CandidateBaselineEntry(
            "src/a.py", CandidateEntryKind.FILE, "b" * 64, 10, False,
        ),),
    )


def _evidence(task_id, evidence_id):
    return EngineeringEvidence(
        evidence_id, task_id, NOW, EngineeringOutcome.SUCCEEDED,
        (), (), (), (f"tool-{evidence_id}",), (f"verifier-{evidence_id}",),
        ("c" * 64,), ("src/a.py",), (),
    )


def _preview(candidate):
    return CandidateTransactionPreview(
        "transaction-1", candidate.candidate_id, candidate.baseline_tree_sha256,
        NOW, (CandidatePreviewItem(
            "src/a.py", CandidateOperationKind.PATCH_FILE,
            "b" * 64, "c" * 64, "text/x-python", 1,
            "--- before\n+++ after", ("content_change",),
        ),), ("verification-1",), "verified", "journal rollback",
    )


def _decision(task_id, preview):
    return CheckpointDecision(
        "decision-1", task_id, "changeset-proposal-1", preview.transaction_id,
        "owner-1", NOW, CheckpointDisposition.APPROVED, "d" * 64, "approved",
    )


def _apply(candidate):
    return CandidateApplyReceipt(
        "transaction-1", candidate.candidate_id, NOW, CandidateApplyStatus.APPLIED,
        ("src/a.py",), (), "e" * 64, False, "applied",
    )


def _commit(task_id):
    action = GitLocalAction(
        "action-1", task_id, "/workspace", GitLocalActionKind.COMMIT,
        None, (), "Commit verified change", "transaction-1",
        ("verification-2",), "1" * 40, NOW,
    )
    receipt = GitLocalActionReceipt(
        "commit-receipt-1", action.action_id, "1" * 40, "2" * 40,
        (), "f" * 64, NOW,
    )
    return action, receipt


def _publication(task_id):
    approval = GitPublicationApproval(
        "publication-approval-1", task_id, "grant-1",
        GitPublicationKind.DRAFT_CHANGE_REQUEST, "/workspace", "origin",
        "a" * 64, "refs/heads/feature", "refs/heads/feature", None,
        "2" * 40, ("2" * 40,), "b" * 64, ("verification-2",),
        "Verified change", "Verified body", "secret.git",
        ("publish feature",), NOW, NOW + timedelta(minutes=5),
    )
    receipt = GitPublicationReceipt(
        "publication-receipt-1", approval.approval_id, "provider-1",
        "origin", approval.target_ref, None, "2" * 40,
        "https://example.invalid/pr/1", True, NOW, "c" * 64,
    )
    return approval, receipt


def _allow_grant(task_id, grant_id, instant):
    if not task_id or grant_id != "grant-1" or instant.tzinfo is None:
        raise PermissionError("grant invalid")


if __name__ == "__main__":
    unittest.main()
