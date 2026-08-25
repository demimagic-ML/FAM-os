import tempfile
import unittest
import subprocess
import hashlib
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from fam_os.adapters.sqlite import (
    SQLiteCandidateChangesetStore, SQLiteCandidateEditStore,
    SQLiteCandidateVerificationStore,
    SQLiteEngineeringLoopStore,
    SQLiteEngineeringPreparationStore,
)
from fam_os.core.engineering import (
    CandidateArtifact, CandidateContentKind, CandidateEditStatus,
    CandidateOperation, CandidateOperationKind,
    CandidateVerificationService, EngineeringEcosystem,
    CheckpointDecision, CheckpointDisposition, candidate_preview_digest,
    EngineeringToolReceipt, ToolQualificationStatus,
    EngineeringGrantScopeKind,
    EngineeringLoopBudget,
    EngineeringLoopStage, EngineeringAuthority,
)
from fam_os.product.engineering_loop_api import ProductEngineeringLoopApi
from fam_os.core.engineering.grants import EngineeringAuthorizationDecision
from tests.contract.schema_repository_fixtures import repository_schema_values
from tests.contract.schema_task_definition_fixtures import task_definition_schema_values
from tests.contract.schema_git_fixtures import git_schema_values


class ProductEngineeringLoopApiTests(unittest.TestCase):
    def test_owner_task_grant_composes_persistent_restart_forgetting_loop(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "loop.sqlite3"
            grants = _Grants("owner-1", "task-1")
            api = ProductEngineeringLoopApi(
                "owner-1", grants, SQLiteEngineeringLoopStore(path),
                Path(temporary) / "candidates",
                SQLiteEngineeringPreparationStore(Path(temporary) / "preparation.sqlite3"),
            )
            api.start(
                "owner-1", _current_definition(),
                EngineeringLoopBudget(100, 100, 10, 100, 10, 100),
            )
            view = api.inspect("owner-1", "task-1")
            self.assertEqual("requested", view["stage"])
            self.assertIsNotNone(api.lifecycle)
            api.close()

            restarted = ProductEngineeringLoopApi(
                "owner-1", grants, SQLiteEngineeringLoopStore(path),
                Path(temporary) / "candidates",
                SQLiteEngineeringPreparationStore(Path(temporary) / "preparation.sqlite3"),
            )
            resumed = restarted.resume("owner-1", "task-1")
            self.assertEqual("requested", resumed["stage"])
            self.assertEqual(1, len(restarted.tasks("owner-1")))
            restarted.close()

    def test_wrong_owner_or_non_task_grant_is_denied(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = SQLiteEngineeringLoopStore(Path(temporary) / "loop.sqlite3")
            api = ProductEngineeringLoopApi(
                "owner-1", _Grants("owner-1", "different"), store,
                Path(temporary) / "candidates",
                SQLiteEngineeringPreparationStore(Path(temporary) / "preparation.sqlite3"),
            )
            with self.assertRaises(PermissionError):
                api.start(
                    "owner-1", _current_definition(),
                    EngineeringLoopBudget(1, 1, 1, 1, 1, 1),
                )
            with self.assertRaises(PermissionError):
                api.tasks("owner-2")
            api.close()

    def test_failed_verification_commands_are_monotonic_and_replay_safe(self):
        with tempfile.TemporaryDirectory() as temporary:
            definition = _current_definition()
            api = ProductEngineeringLoopApi(
                "owner-1", _Grants("owner-1", definition.task.task_id),
                SQLiteEngineeringLoopStore(Path(temporary) / "loop.sqlite3"),
                Path(temporary) / "candidates",
                SQLiteEngineeringPreparationStore(
                    Path(temporary) / "preparation.sqlite3",
                ),
            )
            api.start(
                "owner-1", definition,
                EngineeringLoopBudget(100, 100, 10, 0, 10, 100),
            )
            failed = SimpleNamespace(
                task_id=definition.task.task_id,
                verification_id="verification-failed-1", passed=False,
                status=SimpleNamespace(value="completed"),
                updated_at=datetime.now(timezone.utc),
            )
            interrupted = SimpleNamespace(
                task_id=definition.task.task_id,
                verification_id="verification-interrupted-1", passed=False,
                status=SimpleNamespace(value="recovery_required"),
                updated_at=datetime.now(timezone.utc),
            )

            api.record_failed_candidate_verifications(
                "owner-1", definition.task.task_id, (failed,),
            )
            api.record_failed_candidate_verifications(
                "owner-1", definition.task.task_id, (failed,),
            )
            self.assertEqual(
                9,
                api.remaining_budget(
                    "owner-1", definition.task.task_id,
                )["commands"],
            )
            api.record_failed_candidate_verifications(
                "owner-1", definition.task.task_id, (interrupted,),
            )
            self.assertEqual(
                8,
                api.remaining_budget(
                    "owner-1", definition.task.task_id,
                )["commands"],
            )
            api.close()

    def test_receipt_driver_rechecks_revocation_before_transition(self):
        with tempfile.TemporaryDirectory() as temporary:
            grants = _Grants("owner-1", "task-repository-1")
            api = ProductEngineeringLoopApi(
                "owner-1", grants,
                SQLiteEngineeringLoopStore(Path(temporary) / "loop.sqlite3"),
                Path(temporary) / "candidates",
                SQLiteEngineeringPreparationStore(Path(temporary) / "preparation.sqlite3"),
            )
            api.start(
                "owner-1", _repository_definition(),
                EngineeringLoopBudget(10, 10, 10, 10, 10, 10),
            )
            grants.revoked = True
            analysis = repository_schema_values()[2]
            with self.assertRaises(PermissionError):
                api.lifecycle.record_inspection(analysis)
            self.assertEqual(
                "requested", api.inspect("owner-1", "task-repository-1")["stage"],
            )
            api.close()

    def test_active_preparation_observes_real_git_workspace_and_creates_candidate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            (workspace / "src").mkdir(parents=True)
            (workspace / "src/service.py").write_text("def service():\n    return 1\n")
            subprocess.run(("git", "init", "-q", str(workspace)), check=True)
            subprocess.run(("git", "-C", str(workspace), "add", "src/service.py"), check=True)
            subprocess.run((
                "git", "-C", str(workspace), "-c", "user.name=Test", "-c",
                "user.email=test@example.invalid", "commit", "-q", "-m", "initial",
            ), check=True)
            definition = _workspace_definition(workspace)
            grants = _Grants("owner-1", definition.task.task_id, str(workspace))
            authorizer = _Authorizer()
            verification_store = SQLiteCandidateVerificationStore(
                root / "verifications.sqlite3",
            )
            verification_service = CandidateVerificationService(
                authorizer, _RecipeCatalog(), _VerificationRunner(),
                _ReceiptVerifier(), verification_store,
            )
            changeset_store = SQLiteCandidateChangesetStore(
                root / "changesets.sqlite3",
            )
            api = ProductEngineeringLoopApi(
                "owner-1", grants, SQLiteEngineeringLoopStore(root / "loop.sqlite3"),
                root / "candidates",
                SQLiteEngineeringPreparationStore(root / "preparation.sqlite3"),
                authorizer, SQLiteCandidateEditStore(root / "edits.sqlite3"),
                verification_service, verification_store,
                changeset_store,
            )
            api.start(
                "owner-1", definition,
                EngineeringLoopBudget(100, 100, 10, 100, 100, 100000),
            )
            result = api.prepare("owner-1", definition.task.task_id)
            self.assertEqual("candidate_ready", result["stage"])
            self.assertTrue(result["repository_bundle_id"].startswith("repository-bundle-"))
            resumed = api.prepare("owner-1", definition.task.task_id)
            self.assertEqual(result["repository_bundle_id"], resumed["repository_bundle_id"])
            self.assertEqual(
                result["architecture_proposal_id"],
                resumed["architecture_proposal_id"],
            )
            self.assertEqual(
                result["candidate_id"],
                api.preparation("owner-1", definition.task.task_id).candidate.candidate_id,
            )
            content = b"generated = True\n"
            artifact = CandidateArtifact(
                "artifact-product-1", CandidateContentKind.TEXT, "text/x-python",
                hashlib.sha256(content).hexdigest(), len(content), "owner-request",
            )
            edit = api.edit_candidate(
                "owner-1", definition.task.task_id, edit_id="edit-product-1",
                session_id="session-1", principal_id="principal-1",
                operation=CandidateOperation(
                    "operation-product-1", CandidateOperationKind.CREATE_FILE,
                    "src/generated.py", artifact_id=artifact.artifact_id,
                ),
                artifact=artifact, content=content,
            )
            self.assertEqual(CandidateEditStatus.APPLIED, edit.status)
            self.assertEqual((edit,), api.candidate_edits("owner-1", definition.task.task_id))
            self.assertFalse((workspace / "src/generated.py").exists())
            verification = api.verify_candidate(
                "owner-1", definition.task.task_id,
                verification_id="verification-product-1", session_id="session-1",
                principal_id="principal-1", toolchain="python3",
                recipe_id="engineering.python.test", recipe_version="1.0.0",
            )
            self.assertTrue(verification.passed)
            self.assertEqual("verified", api.inspect("owner-1", definition.task.task_id)["stage"])
            changeset = api.preview_candidate(
                "owner-1", definition.task.task_id, "changeset-product-1",
            )
            self.assertEqual(
                "changeset_approval_required",
                api.inspect("owner-1", definition.task.task_id)["stage"],
            )
            decision = CheckpointDecision(
                "decision-product-1", definition.task.task_id,
                changeset.changeset_id, changeset.changeset_id, "owner-1",
                datetime.now(timezone.utc), CheckpointDisposition.APPROVED,
                candidate_preview_digest(changeset.preview), "Approve exact preview",
            )
            applied = api.apply_candidate(
                "owner-1", definition.task.task_id, changeset.changeset_id,
                decision, session_id="session-1", principal_id="principal-1",
            )
            self.assertEqual("applied", applied.status.value)
            self.assertTrue((workspace / "src/generated.py").is_file())
            self.assertEqual("applied", api.inspect("owner-1", definition.task.task_id)["stage"])
            reverification = api.reverify_candidate(
                "owner-1", definition.task.task_id,
                verification_id="verification-product-postapply-1",
                session_id="session-1", principal_id="principal-1",
                toolchain="python3", recipe_id="engineering.python.test",
                recipe_version="1.0.0",
            )
            self.assertTrue(reverification.passed)
            self.assertNotEqual(
                verification.candidate_id, reverification.candidate_id,
            )
            self.assertEqual("reverified", api.inspect("owner-1", definition.task.task_id)["stage"])
            api.close()
            restarted = ProductEngineeringLoopApi(
                "owner-1", grants, SQLiteEngineeringLoopStore(root / "loop.sqlite3"),
                root / "candidates",
                SQLiteEngineeringPreparationStore(root / "preparation.sqlite3"),
                _Authorizer(), SQLiteCandidateEditStore(root / "edits.sqlite3"),
                None, SQLiteCandidateVerificationStore(root / "verifications.sqlite3"),
                SQLiteCandidateChangesetStore(root / "changesets.sqlite3"),
            )
            self.assertEqual(
                result["candidate_id"],
                restarted.preparation("owner-1", definition.task.task_id).candidate.candidate_id,
            )
            self.assertEqual(
                result["candidate_id"],
                restarted.observe_candidate(
                    "owner-1", definition.task.task_id,
                ).candidate_id,
            )
            self.assertEqual(1, len(restarted.candidate_edits("owner-1", definition.task.task_id)))
            self.assertEqual(2, len(restarted.candidate_verifications(
                "owner-1", definition.task.task_id,
            )))
            self.assertEqual(1, len(restarted.candidate_changesets(
                "owner-1", definition.task.task_id,
            )))
            restarted.close()

    def test_publication_uses_a_separate_task_scoped_publish_grant(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = SQLiteEngineeringLoopStore(Path(temporary) / "loop.sqlite3")
            grants = _PublicationGrants()
            publication = _PublicationService()
            api = ProductEngineeringLoopApi(
                "owner-1", grants, store, Path(temporary) / "candidates",
                SQLiteEngineeringPreparationStore(
                    Path(temporary) / "preparation.sqlite3",
                ),
                publication_service=publication,
            )
            definition = _current_definition()
            api.start(
                "owner-1", definition,
                EngineeringLoopBudget(100, 100, 20, 100, 20, 1000),
            )
            now = datetime.now(timezone.utc)
            for stage, evidence, checkpoint in (
                (EngineeringLoopStage.INSPECTED, "inspect-1", None),
                (EngineeringLoopStage.PROPOSED, "proposal-1", None),
                (EngineeringLoopStage.CANDIDATE_READY, "candidate-1", None),
                (EngineeringLoopStage.VERIFIED, "verify-1", None),
                (EngineeringLoopStage.CHANGESET_APPROVAL_REQUIRED, "changeset-1", None),
                (EngineeringLoopStage.APPLIED, "apply-1", "changeset-1"),
                (EngineeringLoopStage.REVERIFIED, "reverify-1", None),
                (EngineeringLoopStage.COMMITTED, "commit-1", None),
            ):
                api._loop.advance(
                    definition.task.task_id, stage, evidence, instant=now,
                    checkpoint_id=checkpoint,
                )
            approval = replace(
                git_schema_values()[3], task_id=definition.task.task_id,
                grant_id="publish-grant-1", repository_root="/workspace",
                remote_name="origin", target_ref="feature/engineering",
                approved_at=now, expires_at=now + timedelta(minutes=5),
            )
            receipt = api.publish_candidate("owner-1", approval)
            self.assertEqual(approval.approval_id, receipt.approval_id)
            self.assertEqual(
                "published",
                api.inspect("owner-1", definition.task.task_id)["stage"],
            )
            self.assertEqual("publish-grant-1", publication.grant.grant_id)
            api.close()


class _Grants:
    def __init__(self, owner_id, task_id, workspace_root="/workspace"):
        self.revoked = False
        self.grant = SimpleNamespace(
            grant_id="grant-1",
            owner_id=owner_id,
            active_at=lambda _instant: True,
            authorities=_current_definition().task.authorities,
            resource_impact=SimpleNamespace(
                max_wall_seconds=10_000, max_tool_runs=10_000,
                max_changed_files=10_000, max_changed_bytes=10_000_000,
            ),
            scope=SimpleNamespace(
                kind=EngineeringGrantScopeKind.TASK, scope_id=task_id,
                workspace_roots=(workspace_root,),
                toolchains=("python3",), network_hosts=("pypi.org",),
                package_registries=("https://pypi.org/simple",),
                git_remotes=("origin",), git_branches=("feature/engineering",),
            ),
        )

    def usable(self, grant_id):
        return self.grant if grant_id == "grant-1" and not self.revoked else None


class _PublicationGrants(_Grants):
    def __init__(self):
        super().__init__("owner-1", "task-1")
        self.publication = SimpleNamespace(
            grant_id="publish-grant-1", owner_id="owner-1",
            active_at=lambda _instant: True,
            authorities=(EngineeringAuthority.PUBLISH,),
            scope=SimpleNamespace(
                kind=EngineeringGrantScopeKind.TASK, scope_id="task-1",
                workspace_roots=("/workspace",), toolchains=(),
                network_hosts=(), package_registries=(),
                git_remotes=("origin",), git_branches=("feature/engineering",),
            ),
        )

    def usable(self, grant_id):
        if grant_id == self.publication.grant_id:
            return self.publication
        return super().usable(grant_id)


class _PublicationService:
    def publish(self, approval, grant, instant):
        self.grant = grant
        return replace(
            git_schema_values()[4], approval_id=approval.approval_id,
            published_new_object_id=approval.proposed_new_object_id,
            completed_at=instant,
        )

    def close(self):
        pass


class _Authorizer:
    def __init__(self):
        self.index = 0

    def authorize(self, request):
        self.index += 1
        return EngineeringAuthorizationDecision(
            f"decision-{self.index}", request.request_id, request.grant_id,
            request.authority, datetime.now(timezone.utc), True, "authorized",
        )


class _RecipeCatalog:
    def get(self, recipe_id, recipe_version):
        if (recipe_id, recipe_version) != ("engineering.python.test", "1.0.0"):
            raise LookupError("recipe unavailable")
        return SimpleNamespace(
            ecosystem=EngineeringEcosystem.PYTHON,
            executable_path="/usr/bin/python3",
        )


class _VerificationRunner:
    def run(self, task_id, candidate, recipe_id, recipe_version, profile):
        now = datetime.now(timezone.utc)
        return EngineeringToolReceipt(
            "tool-product-1", task_id, candidate.candidate_id, recipe_id,
            "a" * 64, profile.profile_id, "b" * 64, now, now, 0,
            "c" * 64, "d" * 64, (), (),
            ("bubblewrap-unshare-all", "cgroup-v2-systemd", "bounded-rlimits"),
            ToolQualificationStatus.PASSED,
        )


class _ReceiptVerifier:
    def verify(self, receipt, recipe_version):
        return SimpleNamespace(
            passed=True, verifier_ids=("verifier-product-1",), reason="passed",
        )


def _repository_definition():
    from fam_os.core.engineering import EngineeringTaskDefinition, engineering_task_digest
    base = _current_definition()
    task = replace(base.task, task_id="task-repository-1")
    return EngineeringTaskDefinition(
        "definition-task-repository-1", task, base.acceptance_policy_id,
        base.created_at, engineering_task_digest(task),
    )


def _workspace_definition(workspace):
    from fam_os.core.engineering import EngineeringTaskDefinition, engineering_task_digest
    base = _current_definition()
    task = replace(
        base.task, task_id="task-workspace-1", workspace_roots=(str(workspace),),
        intent="Change service implementation",
    )
    return EngineeringTaskDefinition(
        "definition-task-workspace-1", task, base.acceptance_policy_id,
        base.created_at, engineering_task_digest(task),
    )


def _current_definition():
    from fam_os.core.engineering import EngineeringTaskDefinition, engineering_task_digest
    base = task_definition_schema_values()[0]
    now = datetime.now(timezone.utc)
    task = replace(base.task, created_at=now - timedelta(minutes=1), expires_at=now + timedelta(hours=1))
    return EngineeringTaskDefinition(
        base.definition_id, task, base.acceptance_policy_id, now,
        engineering_task_digest(task),
    )


if __name__ == "__main__":
    unittest.main()
