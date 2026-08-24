import hashlib
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fam_os.adapters.filesystem import CandidateWorkspaceAdapter
from fam_os.adapters.sqlite import SQLiteCandidateEditStore
from fam_os.core.engineering import (
    CandidateArtifact, CandidateContentKind, CandidateEditStatus,
    CandidateOperation, CandidateOperationKind, CandidateEditingService,
    EngineeringAuthority, EngineeringOperation, EngineeringTaskDefinition,
    engineering_task_digest,
)
from fam_os.core.engineering.grants import EngineeringAuthorizationDecision
from fam_os.core.engineering.preparation import EngineeringPreparationResult
from tests.contract.schema_repository_fixtures import repository_schema_values
from tests.contract.schema_task_definition_fixtures import task_definition_schema_values


NOW = datetime(2026, 7, 19, 12, 0, tzinfo=timezone.utc)


class CandidateEditingServiceTests(unittest.TestCase):
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
        self.store = SQLiteCandidateEditStore(self.root / "edits.sqlite3")

    def tearDown(self):
        self.store.close()
        self.temporary.cleanup()

    def test_exact_live_authority_edits_only_isolated_candidate_and_persists_receipt(self):
        authorizer = _Authorizer()
        service = CandidateEditingService(
            authorizer, self.adapter, self.store, clock=lambda: NOW,
            identifier=_ids(),
        )
        content = b"value = 2\n"
        operation, artifact = _patch(content)
        result = service.edit(
            self.definition, self.preparation, edit_id="edit-1",
            session_id="session-1", principal_id="principal-1",
            operation=operation, artifact=artifact, content=content,
        )
        self.assertEqual(CandidateEditStatus.APPLIED, result.status)
        self.assertEqual(content, (Path(self.candidate.candidate_workspace) / "src/service.py").read_bytes())
        self.assertEqual("value = 1\n", (self.owner / "src/service.py").read_text())
        self.assertEqual(result, self.store.load("edit-1"))
        self.assertEqual(2, len(authorizer.requests))
        self.assertTrue(all(item.path == "src/service.py" for item in authorizer.requests))
        self.assertTrue(all(item.workspace_root == str(self.owner) for item in authorizer.requests))
        self.assertEqual(result, service.edit(
            self.definition, self.preparation, edit_id="edit-1",
            session_id="session-1", principal_id="principal-1",
            operation=operation, artifact=artifact, content=content,
        ))
        self.assertEqual(2, len(authorizer.requests))

    def test_denied_path_creates_no_intent_or_effect(self):
        service = CandidateEditingService(_Authorizer(), self.adapter, self.store, clock=lambda: NOW)
        content = b"secret\n"
        operation = CandidateOperation(
            "operation-1", CandidateOperationKind.CREATE_FILE, "private/secret.txt",
            artifact_id="artifact-1",
        )
        artifact = _artifact(content)
        with self.assertRaises(PermissionError):
            service.edit(
                self.definition, self.preparation, edit_id="edit-denied",
                session_id="session-1", principal_id="principal-1",
                operation=operation, artifact=artifact, content=content,
            )
        self.assertIsNone(self.store.load("edit-denied"))
        self.assertFalse((Path(self.candidate.candidate_workspace) / "private/secret.txt").exists())

    def test_revocation_between_intent_and_effect_leaves_candidate_unchanged(self):
        authorizer = _Authorizer(deny_at=2)
        service = CandidateEditingService(authorizer, self.adapter, self.store, clock=lambda: NOW)
        content = b"value = 2\n"
        operation, artifact = _patch(content)
        with self.assertRaises(PermissionError):
            service.edit(
                self.definition, self.preparation, edit_id="edit-revoked",
                session_id="session-1", principal_id="principal-1",
                operation=operation, artifact=artifact, content=content,
            )
        record = self.store.load("edit-revoked")
        self.assertEqual(CandidateEditStatus.INTENT_RECORDED, record.status)
        self.assertEqual("value = 1\n", (Path(self.candidate.candidate_workspace) / "src/service.py").read_text())

    def test_crash_after_effect_reconciles_without_reapplying(self):
        authorizer = _Authorizer()
        failing = _FailFinalSave(self.store)
        service = CandidateEditingService(authorizer, self.adapter, failing, clock=lambda: NOW)
        content = b"value = 2\n"
        operation, artifact = _patch(content)
        with self.assertRaises(RuntimeError):
            service.edit(
                self.definition, self.preparation, edit_id="edit-crash",
                session_id="session-1", principal_id="principal-1",
                operation=operation, artifact=artifact, content=content,
            )
        result = CandidateEditingService(
            authorizer, self.adapter, self.store, clock=lambda: NOW,
        ).edit(
            self.definition, self.preparation, edit_id="edit-crash",
            session_id="session-1", principal_id="principal-1",
            operation=operation, artifact=artifact, content=content,
        )
        self.assertEqual(CandidateEditStatus.APPLIED, result.status)
        self.assertEqual(2, len(authorizer.requests))

    def test_cancellation_is_durable_and_has_no_candidate_effect(self):
        service = CandidateEditingService(_Authorizer(), self.adapter, self.store, clock=lambda: NOW)
        content = b"value = 2\n"
        operation, artifact = _patch(content)
        result = service.edit(
            self.definition, self.preparation, edit_id="edit-cancelled",
            session_id="session-1", principal_id="principal-1",
            operation=operation, artifact=artifact, content=content,
            cancelled=lambda: True,
        )
        self.assertEqual(CandidateEditStatus.FAILED, result.status)
        self.assertEqual("cancelled_before_effect", result.failure_code)
        self.assertEqual("value = 1\n", (Path(self.candidate.candidate_workspace) / "src/service.py").read_text())


class _Authorizer:
    def __init__(self, deny_at=None):
        self.deny_at = deny_at
        self.requests = []

    def authorize(self, request):
        self.requests.append(request)
        allowed = len(self.requests) != self.deny_at
        return EngineeringAuthorizationDecision(
            f"decision-{len(self.requests)}", request.request_id, request.grant_id,
            request.authority, NOW, allowed, "authorized" if allowed else "revoked",
        )


class _FailFinalSave:
    def __init__(self, store):
        self.store = store
        self.calls = 0

    def load(self, edit_id):
        return self.store.load(edit_id)

    def begin(self, record):
        self.store.begin(record)

    def usage(self, task_id):
        return self.store.usage(task_id)

    def save(self, expected_revision, record):
        self.calls += 1
        if self.calls == 2:
            raise RuntimeError("injected persistence failure")
        self.store.save(expected_revision, record)


def _definition(owner):
    base = task_definition_schema_values()[0]
    task = replace(
        base.task, task_id="task-repository-1", grant_id="grant-1",
        created_at=NOW - timedelta(minutes=1), expires_at=NOW + timedelta(hours=1),
        workspace_roots=(str(owner),),
        authorities=(EngineeringAuthority.OBSERVE, EngineeringAuthority.PROPOSE, EngineeringAuthority.MODIFY),
        permitted_operations=(EngineeringOperation.READ, EngineeringOperation.CREATE, EngineeringOperation.REPLACE, EngineeringOperation.DELETE, EngineeringOperation.MOVE),
        path_allowlist=("src/**",), path_denylist=("src/private/**",),
        toolchains=(), network_hosts=(), package_registries=(),
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


def _patch(content):
    before = hashlib.sha256(b"value = 1\n").hexdigest()
    return (
        CandidateOperation(
            "operation-1", CandidateOperationKind.PATCH_FILE, "src/service.py",
            expected_before_sha256=before, artifact_id="artifact-1",
        ),
        _artifact(content),
    )


def _artifact(content):
    return CandidateArtifact(
        "artifact-1", CandidateContentKind.TEXT, "text/x-python",
        hashlib.sha256(content).hexdigest(), len(content), "owner-request",
    )


def _ids():
    values = iter(f"request-{index}" for index in range(20))
    return lambda: next(values)


if __name__ == "__main__":
    unittest.main()
