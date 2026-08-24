import hashlib
import json
import sqlite3
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from fam_os.adapters.filesystem import CandidateWorkspaceAdapter
from fam_os.adapters.sqlite import SQLiteCandidateChangesetStore
from fam_os.core.engineering import (
    CandidateArtifact, CandidateChangesetService, CandidateChangesetStatus,
    CandidateContentKind, CandidateEditStatus, CandidateOperation,
    CandidateOperationKind, CheckpointDecision, CheckpointDisposition,
    EngineeringAuthority, EngineeringOperation, EngineeringTaskDefinition,
    IntegrationEnvironmentStartResult, IntegrationEnvironmentStatus,
    integration_environment_plan_digest,
    candidate_preview_digest, candidate_rollback_digest,
    engineering_task_digest,
)
from fam_os.core.engineering.grants import EngineeringAuthorizationDecision
from fam_os.core.engineering.preparation import EngineeringPreparationResult
from fam_os.schemas import SchemaValidationError, encode_document, loads_document
from tests.contract.schema_repository_fixtures import repository_schema_values
from tests.contract.schema_task_definition_fixtures import task_definition_schema_values
from tests.contract.schema_integration_environment_fixtures import (
    integration_environment_schema_values,
)
from tests.contract.schema_database_engineering_fixtures import (
    postgresql_integration_verification_schema_values,
)


NOW = datetime(2026, 7, 19, 14, 0, tzinfo=timezone.utc)


class CandidateChangesetServiceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.owner = self.root / "owner"
        (self.owner / "src").mkdir(parents=True)
        (self.owner / "src/service.py").write_text("value = 1\n")
        self.adapter = CandidateWorkspaceAdapter(self.owner, self.root / "candidates")
        self.candidate = self.adapter.create("task-repository-1", now=NOW)
        self.definition = _definition(self.owner)
        self.preparation = _preparation(self.definition, self.candidate)
        content = b"value = 2\n"
        before = hashlib.sha256(b"value = 1\n").hexdigest()
        self.artifact = CandidateArtifact(
            "artifact-1", CandidateContentKind.TEXT, "text/x-python",
            hashlib.sha256(content).hexdigest(), len(content), "owner-request",
        )
        self.operation = CandidateOperation(
            "operation-1", CandidateOperationKind.PATCH_FILE, "src/service.py",
            expected_before_sha256=before, artifact_id=self.artifact.artifact_id,
        )
        self.adapter.stage_artifact(self.candidate, self.artifact, content)
        self.adapter.execute(
            self.candidate, self.operation, {self.artifact.artifact_id: self.artifact},
        )
        self.edits = (SimpleNamespace(
            status=CandidateEditStatus.APPLIED, operation=self.operation,
            artifact=self.artifact,
        ),)
        self.verifications = (SimpleNamespace(
            passed=True, evidence=SimpleNamespace(evidence_id="evidence-1"),
        ),)
        self.store = SQLiteCandidateChangesetStore(self.root / "changesets.sqlite3")

    def tearDown(self):
        self.store.close()
        self.temporary.cleanup()

    def test_preview_then_exact_owner_decision_applies_journaled_changeset(self):
        authorizer = _Authorizer()
        service = CandidateChangesetService(
            authorizer, self.adapter, self.store, clock=lambda: NOW,
            identifier=_ids(),
        )
        record = service.preview(
            self.definition, self.preparation, self.edits,
            self.verifications, "changeset-1",
        )
        self.assertEqual(CandidateChangesetStatus.PREVIEWED, record.status)
        self.assertEqual("value = 1\n", (self.owner / "src/service.py").read_text())
        result = service.apply(
            self.definition, self.preparation, record, _decision(record),
            session_id="session-1", principal_id="principal-1",
        )
        self.assertEqual(CandidateChangesetStatus.APPLIED, result.status)
        self.assertEqual("value = 2\n", (self.owner / "src/service.py").read_text())
        self.assertEqual(2, len(authorizer.requests))
        self.assertEqual(result, self.store.load("changeset-1"))

    def test_mismatched_preview_digest_has_no_owner_effect(self):
        service = CandidateChangesetService(
            _Authorizer(), self.adapter, self.store, clock=lambda: NOW,
        )
        record = service.preview(
            self.definition, self.preparation, self.edits,
            self.verifications, "changeset-bad",
        )
        with self.assertRaises(PermissionError):
            service.apply(
                self.definition, self.preparation, record,
                replace(_decision(record), proposal_sha256="0" * 64),
                session_id="session-1", principal_id="principal-1",
            )
        self.assertEqual("value = 1\n", (self.owner / "src/service.py").read_text())
        self.assertEqual(CandidateChangesetStatus.PREVIEWED, self.store.load("changeset-bad").status)

    def test_preview_binds_exact_cleaned_integration_environment_evidence(self):
        service = CandidateChangesetService(
            _Authorizer(), self.adapter, self.store, clock=lambda: NOW,
        )
        _spec, base_plan, base_permit, ready, _result = (
            integration_environment_schema_values()
        )
        plan = replace(
            base_plan, task_id=self.definition.task.task_id,
            candidate_id=self.candidate.candidate_id,
            candidate_root=self.candidate.candidate_workspace,
            approved_changeset_id="changeset-integration",
        )
        permit = replace(
            base_permit, environment_id=plan.environment_id,
            approved_changeset_id=plan.approved_changeset_id,
            exact_host_id=plan.exact_host_id,
        )
        ready = replace(
            ready, environment_id=plan.environment_id,
            permit_id=permit.permit_id,
        )
        start = IntegrationEnvironmentStartResult(
            plan.environment_id, integration_environment_plan_digest(plan),
            permit, ready,
        )
        cleanup = replace(
            ready, receipt_id="integration-cleanup-1",
            status=IntegrationEnvironmentStatus.CLEANED,
            cleanup_evidence_ids=("stopped-service-1",),
        )

        record = service.preview(
            self.definition, self.preparation, self.edits,
            self.verifications, "changeset-integration",
            integration_environment_evidence=((plan, start, cleanup),),
        )

        self.assertIn(
            cleanup.receipt_id, record.preview.verification_evidence_ids,
        )
        with self.assertRaisesRegex(ValueError, "integration evidence"):
            service.preview(
                self.definition, self.preparation, self.edits,
                self.verifications, "changeset-integration-substituted",
                integration_environment_evidence=((
                    plan, start,
                    replace(cleanup, permit_id="substituted-permit"),
                ),),
            )

    def test_preview_binds_postgresql_lifecycle_to_exact_cleaned_runtime(self):
        service = CandidateChangesetService(
            _Authorizer(), self.adapter, self.store, clock=lambda: NOW,
        )
        _spec, base_plan, base_permit, ready, _result = (
            integration_environment_schema_values()
        )
        changeset_id = "changeset-postgresql"
        environment = replace(
            base_plan,
            task_id=self.definition.task.task_id,
            candidate_id=self.candidate.candidate_id,
            candidate_root=self.candidate.candidate_workspace,
            approved_changeset_id=changeset_id,
        )
        permit = replace(
            base_permit,
            environment_id=environment.environment_id,
            approved_changeset_id=changeset_id,
            exact_host_id=environment.exact_host_id,
        )
        ready = replace(
            ready,
            environment_id=environment.environment_id,
            permit_id=permit.permit_id,
        )
        start = IntegrationEnvironmentStartResult(
            environment.environment_id,
            integration_environment_plan_digest(environment),
            permit,
            ready,
        )
        cleanup = replace(
            ready,
            receipt_id="postgresql-cleanup-1",
            status=IntegrationEnvironmentStatus.CLEANED,
            cleanup_evidence_ids=("removed-postgresql",),
        )
        pg_plan, pg_receipt = postgresql_integration_verification_schema_values()
        service_spec = environment.services[0]
        service_receipt = ready.services[0]
        pg_plan = replace(
            pg_plan,
            task_id=self.definition.task.task_id,
            candidate_id=self.candidate.candidate_id,
            environment_id=environment.environment_id,
            service_id=service_spec.service_id,
            approved_changeset_id=changeset_id,
            exact_host_id=environment.exact_host_id,
        )
        pg_receipt = replace(
            pg_receipt,
            plan_id=pg_plan.plan_id,
            task_id=pg_plan.task_id,
            candidate_id=pg_plan.candidate_id,
            environment_id=pg_plan.environment_id,
            service_id=pg_plan.service_id,
            runtime_id=service_receipt.runtime_id,
            permit_id=permit.permit_id,
            applied_asset_ids=tuple(
                item.asset_id for item in pg_plan.migration_assets
            ),
        )

        record = service.preview(
            self.definition, self.preparation, self.edits,
            self.verifications, changeset_id,
            integration_environment_evidence=((environment, start, cleanup),),
            postgresql_evidence=((pg_plan, pg_receipt),),
        )

        self.assertIn(
            pg_receipt.receipt_id,
            record.preview.verification_evidence_ids,
        )
        with self.assertRaisesRegex(ValueError, "PostgreSQL verification"):
            service.preview(
                self.definition, self.preparation, self.edits,
                self.verifications, changeset_id,
                integration_environment_evidence=((
                    environment, start, cleanup,
                ),),
                postgresql_evidence=((
                    pg_plan,
                    replace(pg_receipt, runtime_id="substituted-runtime"),
                ),),
            )

    def test_revocation_after_apply_intent_prevents_owner_effect(self):
        service = CandidateChangesetService(
            _Authorizer(deny_at=2), self.adapter, self.store,
            clock=lambda: NOW, identifier=_ids(),
        )
        record = service.preview(
            self.definition, self.preparation, self.edits,
            self.verifications, "changeset-revoked",
        )
        with self.assertRaises(PermissionError):
            service.apply(
                self.definition, self.preparation, record, _decision(record),
                session_id="session-1", principal_id="principal-1",
            )
        self.assertEqual("value = 1\n", (self.owner / "src/service.py").read_text())
        self.assertEqual(CandidateChangesetStatus.APPLY_INTENT, self.store.load("changeset-revoked").status)

    def test_crash_after_owner_effect_recovers_from_adapter_journal(self):
        failing = _FailFinalSave(self.store)
        service = CandidateChangesetService(
            _Authorizer(), self.adapter, failing, clock=lambda: NOW,
            identifier=_ids(),
        )
        record = service.preview(
            self.definition, self.preparation, self.edits,
            self.verifications, "changeset-crash",
        )
        with self.assertRaises(RuntimeError):
            service.apply(
                self.definition, self.preparation, record, _decision(record),
                session_id="session-1", principal_id="principal-1",
            )
        self.assertEqual("value = 2\n", (self.owner / "src/service.py").read_text())
        pending = self.store.load("changeset-crash")
        recovered = CandidateChangesetService(
            _Authorizer(), self.adapter, self.store, clock=lambda: NOW,
        ).recover(self.preparation, pending)
        self.assertEqual(CandidateChangesetStatus.ROLLED_BACK, recovered.status)
        self.assertEqual("value = 1\n", (self.owner / "src/service.py").read_text())

    def test_explicit_rollback_is_approved_persisted_and_replay_safe(self):
        service = CandidateChangesetService(
            _Authorizer(), self.adapter, self.store, clock=lambda: NOW,
            identifier=_ids(),
        )
        record = service.preview(
            self.definition, self.preparation, self.edits,
            self.verifications, "changeset-rollback",
        )
        applied = service.apply(
            self.definition, self.preparation, record, _decision(record),
            session_id="session-1", principal_id="principal-1",
        )
        head = "3" * 40
        decision = _rollback_decision(applied, head)
        rolled_back = service.rollback(
            self.definition, self.preparation, applied, decision, head,
            session_id="session-1", principal_id="principal-1",
        )
        self.assertEqual(
            CandidateChangesetStatus.EXPLICITLY_ROLLED_BACK,
            rolled_back.status,
        )
        self.assertEqual("value = 1\n", (self.owner / "src/service.py").read_text())
        self.assertTrue(rolled_back.rollback_receipt.rollback_complete)
        self.assertEqual(
            rolled_back,
            service.rollback(
                self.definition, self.preparation, rolled_back,
                decision, head, session_id="session-1",
                principal_id="principal-1",
            ),
        )

    def test_explicit_rollback_preserves_concurrent_owner_change(self):
        service = CandidateChangesetService(
            _Authorizer(), self.adapter, self.store, clock=lambda: NOW,
            identifier=_ids(),
        )
        record = service.preview(
            self.definition, self.preparation, self.edits,
            self.verifications, "changeset-drift",
        )
        applied = service.apply(
            self.definition, self.preparation, record, _decision(record),
            session_id="session-1", principal_id="principal-1",
        )
        (self.owner / "src/service.py").write_text("owner = 'newer'\n")
        head = "4" * 40
        result = service.rollback(
            self.definition, self.preparation, applied,
            _rollback_decision(applied, head), head,
            session_id="session-1", principal_id="principal-1",
        )
        self.assertEqual(
            CandidateChangesetStatus.ROLLBACK_RECOVERY_REQUIRED,
            result.status,
        )
        self.assertEqual("owner = 'newer'\n", (self.owner / "src/service.py").read_text())
        self.assertEqual(
            ("src/service.py",),
            result.rollback_receipt.preserved_owner_paths,
        )

    def test_pre_rollback_persisted_shape_migrates_only_inside_store(self):
        service = CandidateChangesetService(
            _Authorizer(), self.adapter, self.store, clock=lambda: NOW,
            identifier=_ids(),
        )
        record = service.preview(
            self.definition, self.preparation, self.edits,
            self.verifications, "changeset-legacy",
        )
        document = encode_document(record)
        for field in (
            "rollback_decision", "rollback_authorization_decision_ids",
            "rollback_receipt",
        ):
            del document["payload"][field]
        serialized = json.dumps(document, separators=(",", ":"))
        with self.assertRaises(SchemaValidationError):
            loads_document(serialized)
        with sqlite3.connect(self.root / "changesets.sqlite3") as database:
            database.execute(
                "UPDATE candidate_changeset SET document=? WHERE changeset_id=?",
                (serialized, record.changeset_id),
            )
        migrated = self.store.load(record.changeset_id)
        self.assertEqual(record, migrated)


class _Authorizer:
    def __init__(self, deny_at=None):
        self.deny_at = deny_at
        self.requests = []

    def authorize(self, request):
        self.requests.append(request)
        allowed = len(self.requests) != self.deny_at
        return EngineeringAuthorizationDecision(
            f"authorization-{len(self.requests)}", request.request_id,
            request.grant_id, request.authority, NOW, allowed,
            "authorized" if allowed else "revoked",
        )


class _FailFinalSave:
    def __init__(self, store):
        self.store = store
        self.saves = 0

    def begin(self, record):
        self.store.begin(record)

    def save(self, expected, record):
        self.saves += 1
        if self.saves == 3:
            raise RuntimeError("injected post-effect crash")
        self.store.save(expected, record)


def _definition(owner):
    base = task_definition_schema_values()[0]
    task = replace(
        base.task, task_id="task-repository-1", created_at=NOW - timedelta(minutes=1),
        expires_at=NOW + timedelta(hours=1), workspace_roots=(str(owner),),
        authorities=(EngineeringAuthority.OBSERVE, EngineeringAuthority.PROPOSE,
                     EngineeringAuthority.MODIFY, EngineeringAuthority.EXECUTE),
        permitted_operations=(EngineeringOperation.READ, EngineeringOperation.REPLACE,
                              EngineeringOperation.RUN_TOOL),
        path_allowlist=("src/**",), path_denylist=(".git/**",),
        toolchains=("python3",), network_hosts=(), package_registries=(),
        git_remote=None, git_branch=None,
    )
    return EngineeringTaskDefinition(
        "definition-task-repository-1", task, "acceptance-1", NOW,
        engineering_task_digest(task),
    )


def _preparation(definition, candidate):
    evidence, _request, analysis, proposal, _graph, _event = repository_schema_values()
    return EngineeringPreparationResult(
        definition.definition_id, evidence, analysis, proposal, candidate,
    )


def _decision(record):
    return CheckpointDecision(
        "decision-1", record.task_id, record.changeset_id, record.changeset_id,
        "owner-1", NOW, CheckpointDisposition.APPROVED,
        candidate_preview_digest(record.preview), "Approve exact changeset",
    )


def _rollback_decision(record, head):
    rollback_id = f"rollback-{record.changeset_id}"
    return CheckpointDecision(
        f"decision-{rollback_id}", record.task_id, rollback_id, rollback_id,
        "owner-1", NOW, CheckpointDisposition.APPROVED,
        candidate_rollback_digest(record, head), "Approve exact rollback",
    )


def _ids():
    values = iter(f"request-{index}" for index in range(20))
    return lambda: next(values)


if __name__ == "__main__":
    unittest.main()
