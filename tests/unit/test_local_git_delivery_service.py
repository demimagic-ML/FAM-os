import subprocess
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fam_os.adapters.git import LocalGitAdapter
from fam_os.adapters.sqlite import SQLiteLocalGitDeliveryStore
from fam_os.core.engineering import (
    CandidateApplyStatus, CandidateChangesetStatus,
    CheckpointDecision, CheckpointDisposition,
    EngineeringAuthorizationDecision, EngineeringTaskDefinition,
    LocalGitDeliveryService, LocalGitDeliveryStatus, engineering_task_digest,
    candidate_rollback_digest,
)
from tests.contract.schema_candidate_changeset_fixtures import (
    candidate_changeset_schema_values,
)
from tests.contract.schema_task_definition_fixtures import (
    task_definition_schema_values,
)


class LocalGitDeliveryServiceTests(unittest.TestCase):
    def test_precommit_rollback_binds_head_and_rejects_ref_drift(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repository"
            (root / "src").mkdir(parents=True)
            target = root / "src/module.py"
            target.write_text("before = True\n")
            _git(root, "init", "-q", "-b", "main", str(root), cwd=None)
            _git(root, "add", "src/module.py")
            _git(
                root, "-c", "user.name=Fixture", "-c",
                "user.email=fixture@example.invalid", "commit", "-q",
                "-m", "initial",
            )
            target.write_text("after = True\n")
            definition = _definition(root)
            changeset = candidate_changeset_schema_values()[0]
            store = SQLiteLocalGitDeliveryStore(
                Path(temporary) / "delivery.sqlite3",
            )
            service = LocalGitDeliveryService(
                _Authorizer(), LocalGitAdapter(), store,
            )

            preview = service.precommit_rollback_preview(definition, changeset)
            self.assertEqual(_git(root, "rev-parse", "HEAD"), preview[
                "expected_head_object_id"
            ])
            self.assertIn(
                "Do not create or rewrite a Git commit.",
                preview["consequences"],
            )
            (root / "owner.txt").write_text("owner\n")
            _git(root, "add", "owner.txt")
            _git(
                root, "-c", "user.name=Fixture", "-c",
                "user.email=fixture@example.invalid", "commit", "-q",
                "-m", "owner commit",
            )
            with self.assertRaisesRegex(RuntimeError, "Git head changed"):
                service.require_precommit_rollback_head(
                    definition, changeset, preview["expected_head_object_id"],
                )
            self.assertEqual("after = True\n", target.read_text())
            store.close()

    def test_commit_reconciles_after_effect_before_receipt_persistence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repository"
            (root / "src").mkdir(parents=True)
            target = root / "src/module.py"
            target.write_text("before = True\n")
            subprocess.run(("git", "init", "-q", "-b", "main", str(root)), check=True)
            subprocess.run(("git", "-C", str(root), "add", "src/module.py"), check=True)
            subprocess.run((
                "git", "-C", str(root), "-c", "user.name=Fixture", "-c",
                "user.email=fixture@example.invalid", "commit", "-q", "-m", "initial",
            ), check=True)
            target.write_text("after = True\n")
            definition = _definition(root)
            changeset = candidate_changeset_schema_values()[0]
            store = SQLiteLocalGitDeliveryStore(Path(temporary) / "delivery.sqlite3")
            interrupted = _InterruptCommitSave(store)
            authorizer = _Authorizer()
            service = LocalGitDeliveryService(
                authorizer, LocalGitAdapter(), interrupted,
            )
            with self.assertRaisesRegex(RuntimeError, "persistence interruption"):
                service.commit(
                    definition, changeset, session_id="session-1",
                    principal_id="owner-1", verification_evidence_ids=("verify-1",),
                    message="FAM: verified change",
                )

            recovered = LocalGitDeliveryService(
                authorizer, LocalGitAdapter(), store,
            ).commit(
                definition, changeset, session_id="session-1",
                principal_id="owner-1", verification_evidence_ids=("verify-1",),
                message="FAM: verified change",
            )
            self.assertEqual(LocalGitDeliveryStatus.COMMITTED, recovered.status)
            self.assertIsNotNone(recovered.branch_action)
            self.assertIsNotNone(recovered.branch_receipt)
            self.assertTrue(_git(root, "branch", "--show-current").startswith("fam/"))
            self.assertEqual(
                "FAM: verified change",
                subprocess.run(
                    ("git", "-C", str(root), "show", "-s", "--format=%B", "HEAD"),
                    check=True, capture_output=True, text=True,
                ).stdout.strip(),
            )
            self.assertEqual(
                2,
                int(subprocess.run(
                    ("git", "-C", str(root), "rev-list", "--count", "HEAD"),
                    check=True, capture_output=True, text=True,
                ).stdout),
            )
            store.close()

    def test_branch_effect_before_receipt_persistence_reconciles_exactly(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repository"
            (root / "src").mkdir(parents=True)
            target = root / "src/module.py"
            target.write_text("before = True\n")
            _git(root, "init", "-q", "-b", "main", str(root), cwd=None)
            _git(root, "add", "src/module.py")
            _git(
                root, "-c", "user.name=Fixture", "-c",
                "user.email=fixture@example.invalid", "commit", "-q",
                "-m", "initial",
            )
            target.write_text("after = True\n")
            definition = _definition(root)
            changeset = candidate_changeset_schema_values()[0]
            store = SQLiteLocalGitDeliveryStore(
                Path(temporary) / "delivery.sqlite3",
            )
            interrupted = _InterruptBranchSave(store)
            authorizer = _Authorizer()
            service = LocalGitDeliveryService(
                authorizer, LocalGitAdapter(), interrupted,
            )
            with self.assertRaisesRegex(RuntimeError, "branch persistence interruption"):
                service.commit(
                    definition, changeset, session_id="session-1",
                    principal_id="owner-1", verification_evidence_ids=("verify-1",),
                    message="FAM: verified change",
                )
            created_branch = _git(root, "branch", "--show-current")
            self.assertTrue(created_branch.startswith("fam/"))

            recovered = LocalGitDeliveryService(
                authorizer, LocalGitAdapter(), store,
            ).commit(
                definition, changeset, session_id="session-1",
                principal_id="owner-1", verification_evidence_ids=("verify-1",),
                message="FAM: verified change",
            )
            self.assertEqual(LocalGitDeliveryStatus.COMMITTED, recovered.status)
            self.assertEqual(created_branch, _git(root, "branch", "--show-current"))
            self.assertEqual("2", _git(root, "rev-list", "--count", "HEAD"))
            store.close()

    def test_existing_derived_feature_branch_stops_without_protected_ref_commit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repository"
            (root / "src").mkdir(parents=True)
            target = root / "src/module.py"
            target.write_text("before = True\n")
            _git(root, "init", "-q", "-b", "main", str(root), cwd=None)
            _git(root, "add", "src/module.py")
            _git(
                root, "-c", "user.name=Fixture", "-c",
                "user.email=fixture@example.invalid", "commit", "-q",
                "-m", "initial",
            )
            target.write_text("after = True\n")
            definition = _definition(root)
            changeset = candidate_changeset_schema_values()[0]
            first_store = SQLiteLocalGitDeliveryStore(
                Path(temporary) / "first.sqlite3",
            )
            first = LocalGitDeliveryService(
                _Authorizer(), LocalGitAdapter(), first_store,
            ).commit(
                definition, changeset, session_id="session-1",
                principal_id="owner-1", verification_evidence_ids=("verify-1",),
                message="FAM: verified change",
            )
            feature = first.branch_action.branch_name
            first_store.close()
            _git(root, "switch", "main")
            target.write_text("after = True\n")
            collision_store = SQLiteLocalGitDeliveryStore(
                Path(temporary) / "collision.sqlite3",
            )
            with self.assertRaisesRegex(RuntimeError, "feature branch state changed"):
                LocalGitDeliveryService(
                    _Authorizer(), LocalGitAdapter(), collision_store,
                ).commit(
                    definition, changeset, session_id="session-2",
                    principal_id="owner-1", verification_evidence_ids=("verify-2",),
                    message="FAM: second verified change",
                )
            self.assertEqual("main", _git(root, "branch", "--show-current"))
            self.assertEqual("1", _git(root, "rev-list", "--count", "main"))
            self.assertEqual(feature, first.branch_action.branch_name)
            collision_store.close()

    def test_explicit_rollback_creates_separate_commit_and_reconciles(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repository"
            (root / "src").mkdir(parents=True)
            target = root / "src/module.py"
            target.write_text("before = True\n")
            _git(root, "init", "-q", "-b", "main", str(root), cwd=None)
            _git(root, "add", "src/module.py")
            _git(
                root, "-c", "user.name=Fixture", "-c",
                "user.email=fixture@example.invalid", "commit", "-q",
                "-m", "initial",
            )
            target.write_text("after = True\n")
            definition = _definition(root)
            changeset = candidate_changeset_schema_values()[0]
            store = SQLiteLocalGitDeliveryStore(
                Path(temporary) / "delivery.sqlite3",
            )
            service = LocalGitDeliveryService(
                _Authorizer(), LocalGitAdapter(), store,
            )
            original = service.commit(
                definition, changeset, session_id="session-1",
                principal_id="owner-1", verification_evidence_ids=("verify-1",),
                message="FAM: verified change",
            )
            target.write_text("before = True\n")
            head = original.commit_receipt.after_object_id
            rollback_id = f"rollback-{changeset.changeset_id}"
            decision = CheckpointDecision(
                f"decision-{rollback_id}", changeset.task_id,
                rollback_id, rollback_id, "owner-1",
                changeset.updated_at, CheckpointDisposition.APPROVED,
                candidate_rollback_digest(changeset, head),
                "Approve exact rollback",
            )
            rollback_receipt = replace(
                changeset.receipt,
                status=CandidateApplyStatus.ROLLED_BACK,
                applied_paths=(), rollback_complete=True,
                message="explicit rollback completed",
            )
            rolled_back = replace(
                changeset,
                status=CandidateChangesetStatus.EXPLICITLY_ROLLED_BACK,
                rollback_decision=decision,
                rollback_authorization_decision_ids=("rollback-auth-1",),
                rollback_receipt=rollback_receipt,
            )
            preview = service.rollback_preview(definition, rolled_back)
            self.assertEqual(rollback_id, preview["rollback_id"])
            delivery = service.rollback(
                definition, rolled_back, session_id="session-1",
                principal_id="owner-1", message="FAM rollback: verified change",
            )
            self.assertEqual(LocalGitDeliveryStatus.COMMITTED, delivery.status)
            self.assertEqual("before = True\n", target.read_text())
            self.assertEqual("3", _git(root, "rev-list", "--count", "HEAD"))
            self.assertEqual(
                "FAM rollback: verified change",
                _git(root, "show", "-s", "--format=%B", "HEAD"),
            )
            retried = service.rollback(
                definition, rolled_back, session_id="session-1",
                principal_id="owner-1", message="FAM rollback: verified change",
            )
            self.assertEqual(delivery, retried)
            self.assertEqual("3", _git(root, "rev-list", "--count", "HEAD"))
            store.close()


class _InterruptCommitSave:
    def __init__(self, store):
        self.store = store
        self.failed = False

    def load(self, delivery_id):
        return self.store.load(delivery_id)

    def begin(self, record):
        return self.store.begin(record)

    def save(self, expected_revision, record):
        if record.status is LocalGitDeliveryStatus.COMMITTED and not self.failed:
            self.failed = True
            raise RuntimeError("persistence interruption")
        return self.store.save(expected_revision, record)


class _InterruptBranchSave:
    def __init__(self, store):
        self.store = store
        self.failed = False

    def load(self, delivery_id):
        return self.store.load(delivery_id)

    def begin(self, record):
        return self.store.begin(record)

    def save(self, expected_revision, record):
        if (
            record.status is LocalGitDeliveryStatus.INTENT_RECORDED
            and record.branch_receipt is not None
            and not self.failed
        ):
            self.failed = True
            raise RuntimeError("branch persistence interruption")
        return self.store.save(expected_revision, record)


class _Authorizer:
    def __init__(self):
        self.index = 0

    def authorize(self, request):
        self.index += 1
        return EngineeringAuthorizationDecision(
            f"authorization-{self.index}", request.request_id, request.grant_id,
            request.authority, datetime.now(timezone.utc), True, "authorized",
        )


def _definition(workspace):
    base = task_definition_schema_values()[0]
    now = datetime.now(timezone.utc)
    task = replace(
        base.task, workspace_roots=(str(workspace),),
        created_at=now - timedelta(minutes=1), expires_at=now + timedelta(hours=1),
    )
    return EngineeringTaskDefinition(
        base.definition_id, task, base.acceptance_policy_id, now,
        engineering_task_digest(task),
    )


def _git(root, *args, cwd=True):
    command = ("git", "-C", str(root), *args) if cwd else ("git", *args)
    return subprocess.run(
        command, check=True, capture_output=True, text=True,
    ).stdout.strip()


if __name__ == "__main__":
    unittest.main()
