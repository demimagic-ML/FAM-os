import http.cookiejar
import base64
import hashlib
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from fam_os.console.http import ConsoleHttpServer
from fam_os.console.provider import LocalConsoleProvider
from fam_os.schemas import encode_document
from fam_os.core.engineering import (
    CandidateArtifact, CandidateContentKind, CandidateOperation,
    CandidateOperationKind, EngineeringIncidentStage,
)
from tests.contract.schema_candidate_edit_fixtures import candidate_edit_schema_values
from tests.contract.schema_candidate_verification_fixtures import candidate_verification_schema_values
from tests.contract.schema_candidate_changeset_fixtures import candidate_changeset_schema_values
from tests.contract.schema_task_definition_fixtures import task_definition_schema_values
from tests.contract.schema_git_fixtures import git_schema_values
from tests.contract.schema_incident_fixtures import incident_schema_values
from tests.contract.schema_review_fixtures import review_schema_values
from tests.contract.schema_documentation_fixtures import documentation_schema_values
from tests.contract.schema_diagnostics_fixtures import diagnostics_schema_values
from tests.contract.schema_database_engineering_fixtures import (
    database_engineering_schema_values, database_postapply_schema_values,
)


class ConsoleEngineeringLoopTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.api = _LoopApi()
        self.server = ConsoleHttpServer(
            ("127.0.0.1", 0), LocalConsoleProvider(Path(self.temporary.name)),
            "x" * 32, engineering_loop_api=self.api,
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temporary.cleanup()

    def test_authenticated_owner_starts_lists_and_resumes_task(self):
        with self.assertRaises(urllib.error.HTTPError) as denied:
            urllib.request.urlopen(self.base + "/api/v1/engineering/tasks")
        self.assertEqual(401, denied.exception.code)
        opener, csrf = _session(self.base)
        started = _post(opener, self.base + "/api/v1/engineering/tasks/start", csrf, {
            "owner_id": "owner-1",
            "definition": encode_document(task_definition_schema_values()[0]),
            "budget": {
                "maximum_tokens": 10, "maximum_wall_seconds": 10,
                "maximum_commands": 10, "maximum_network_bytes": 10,
                "maximum_files": 10, "maximum_storage_bytes": 10,
            },
            "confirmed": True,
        })
        self.assertEqual("task-1", started["task_id"])
        resumed = _post(
            opener, self.base + "/api/v1/engineering/tasks/task-1/resume", csrf,
            {"owner_id": "owner-1", "confirmed": True},
        )
        self.assertEqual("requested", resumed["stage"])
        prepared = _post(
            opener, self.base + "/api/v1/engineering/tasks/task-1/prepare", csrf,
            {"owner_id": "owner-1", "confirmed": True},
        )
        self.assertEqual("candidate_ready", prepared["stage"])
        content = b"generated = True\n"
        artifact = CandidateArtifact(
            "artifact-console-1", CandidateContentKind.TEXT, "text/x-python",
            hashlib.sha256(content).hexdigest(), len(content), "owner-request",
        )
        edited = _post(
            opener, self.base + "/api/v1/engineering/tasks/task-1/edit", csrf,
            {
                "owner_id": "owner-1", "edit_id": "edit-console-1",
                "session_id": "session-1", "principal_id": "principal-1",
                "operation": encode_document(CandidateOperation(
                    "operation-console-1", CandidateOperationKind.CREATE_FILE,
                    "src/generated.py", artifact_id=artifact.artifact_id,
                )),
                "artifact": encode_document(artifact),
                "content_base64": base64.b64encode(content).decode(),
                "confirmed": True,
            },
        )
        self.assertEqual("edit-1", edited["edit"]["payload"]["edit_id"])
        edits = _get(opener, self.base + "/api/v1/engineering/tasks/task-1/edits")
        self.assertEqual(1, len(edits["edits"]))
        verified = _post(
            opener, self.base + "/api/v1/engineering/tasks/task-1/verify", csrf,
            {
                "owner_id": "owner-1", "verification_id": "verification-1",
                "session_id": "session-1", "principal_id": "principal-1",
                "toolchain": "python3", "recipe_id": "engineering.python.test",
                "recipe_version": "1.0.0", "confirmed": True,
            },
        )
        self.assertEqual(
            "verification-1", verified["verification"]["payload"]["verification_id"],
        )
        verifications = _get(
            opener, self.base + "/api/v1/engineering/tasks/task-1/verifications",
        )
        self.assertEqual(1, len(verifications["verifications"]))
        previewed = _post(
            opener, self.base + "/api/v1/engineering/tasks/task-1/preview", csrf,
            {"owner_id": "owner-1", "changeset_id": "transaction-1", "confirmed": True},
        )
        self.assertEqual("transaction-1", previewed["changeset"]["payload"]["changeset_id"])
        fixture = candidate_changeset_schema_values()[0]
        applied = _post(
            opener, self.base + "/api/v1/engineering/tasks/task-1/apply", csrf,
            {
                "owner_id": "owner-1", "changeset_id": "transaction-1",
                "decision": encode_document(fixture.decision),
                "session_id": "session-1", "principal_id": "principal-1",
                "confirmed": True,
            },
        )
        self.assertEqual("applied", applied["changeset"]["payload"]["status"])
        reverified = _post(
            opener, self.base + "/api/v1/engineering/tasks/task-1/reverify", csrf,
            {
                "owner_id": "owner-1", "verification_id": "verification-2",
                "session_id": "session-1", "principal_id": "principal-1",
                "toolchain": "python3", "recipe_id": "engineering.python.test",
                "recipe_version": "1.0.0", "confirmed": True,
            },
        )
        self.assertEqual("verification-1", reverified["verification"]["payload"]["verification_id"])
        changesets = _get(
            opener, self.base + "/api/v1/engineering/tasks/task-1/changesets",
        )
        self.assertEqual(1, len(changesets["changesets"]))
        listed = _get(opener, self.base + "/api/v1/engineering/tasks")
        self.assertEqual("task-1", listed["tasks"][0]["task_id"])
        approval = git_schema_values()[3]
        published = _post(
            opener, self.base + "/api/v1/engineering/tasks/task-1/publish", csrf,
            {
                "owner_id": "owner-1", "approval": encode_document(approval),
                "confirmed": True,
            },
        )
        self.assertEqual(
            approval.approval_id,
            published["publication"]["payload"]["approval_id"],
        )
        incidents = _get(
            opener, self.base + "/api/v1/engineering/tasks/task-1/incidents",
        )
        self.assertEqual(
            "incident-1", incidents["incidents"][0]["payload"]["incident_id"],
        )
        self.assertEqual(
            "preservation-1", incidents["evidence"][0]["payload"]["receipt_id"],
        )
        advanced = _post(
            opener,
            self.base + "/api/v1/engineering/tasks/task-1/incident-advance",
            csrf,
            {
                "owner_id": "owner-1", "incident_id": "incident-1",
                "stage": EngineeringIncidentStage.REMEDIATION_PROPOSED.value,
                "evidence_id": "changeset-remediation-1", "confirmed": True,
            },
        )
        self.assertEqual(
            EngineeringIncidentStage.REMEDIATION_PROPOSED.value,
            advanced["incident"]["payload"]["stage"],
        )
        reviews = _get(
            opener, self.base + "/api/v1/engineering/tasks/task-1/reviews",
        )
        self.assertEqual(
            "review-1", reviews["reviews"][0]["payload"]["checkpoint_id"],
        )
        self.assertEqual(
            "selection-1", reviews["evidence"][1]["payload"]["selection_id"],
        )
        documentation = _get(
            opener,
            self.base + "/api/v1/engineering/tasks/task-1/documentation",
        )
        self.assertEqual(6, len(documentation["documentation"]))
        diagnostics = _get(
            opener,
            self.base + "/api/v1/engineering/tasks/task-1/runtime-diagnostics",
        )
        self.assertEqual(
            "diagnostic-request-1",
            diagnostics["requests"][0]["payload"]["request_id"],
        )
        self.assertEqual(
            "diagnostic-receipt-1",
            diagnostics["receipts"][0]["payload"]["receipt_id"],
        )
        database = _get(
            opener, self.base + "/api/v1/engineering/tasks/task-1/database",
        )
        self.assertEqual(
            "database-plan-1", database["plans"][0]["payload"]["plan_id"],
        )
        self.assertEqual(
            "database-receipt-1",
            database["verifications"][0]["payload"]["receipt_id"],
        )
        self.assertTrue(database["postapply"][0]["payload"]["passed"])

    def test_start_requires_csrf_and_confirmation(self):
        opener, csrf = _session(self.base)
        body = {
            "owner_id": "owner-1",
            "definition": encode_document(task_definition_schema_values()[0]),
            "budget": {name: 1 for name in (
                "maximum_tokens", "maximum_wall_seconds", "maximum_commands",
                "maximum_network_bytes", "maximum_files", "maximum_storage_bytes",
            )},
            "confirmed": False,
        }
        with self.assertRaises(urllib.error.HTTPError) as denied:
            _post(opener, self.base + "/api/v1/engineering/tasks/start", csrf, body)
        self.assertEqual(403, denied.exception.code)


class _LoopApi:
    owner_id = "owner-1"

    def __init__(self):
        self.stage = "requested"
        self.incident = incident_schema_values()[0]
        self.incident_evidence = incident_schema_values()[1]

    def start(self, owner_id, definition, budget):
        return type("State", (), {"task_id": definition.task.task_id})()

    def inspect(self, owner_id, task_id):
        return self._view(task_id)

    def tasks(self, owner_id):
        return (self._view("task-1"),)

    def advance(self, owner_id, task_id, stage, evidence_id, **kwargs):
        self.stage = stage.value
        return self._view(task_id)

    def resume(self, owner_id, task_id):
        return self._view(task_id)

    def prepare(self, owner_id, task_id):
        self.stage = "candidate_ready"
        return self._view(task_id)

    def edit_candidate(self, owner_id, task_id, **kwargs):
        return candidate_edit_schema_values()[0]

    def candidate_edits(self, owner_id, task_id):
        return candidate_edit_schema_values()

    def verify_candidate(self, owner_id, task_id, **kwargs):
        return candidate_verification_schema_values()[0]

    def reverify_candidate(self, owner_id, task_id, **kwargs):
        return candidate_verification_schema_values()[0]

    def candidate_verifications(self, owner_id, task_id):
        return candidate_verification_schema_values()

    def preview_candidate(self, owner_id, task_id, changeset_id):
        return candidate_changeset_schema_values()[0]

    def apply_candidate(self, owner_id, task_id, changeset_id, decision, **kwargs):
        return candidate_changeset_schema_values()[0]

    def candidate_changesets(self, owner_id, task_id):
        return candidate_changeset_schema_values()

    def publish_candidate(self, owner_id, approval):
        return git_schema_values()[4]

    def incidents_for_task(self, owner_id, task_id):
        return (self.incident,)

    def incident_evidence_for_task(self, owner_id, task_id):
        return (self.incident_evidence,)

    def inspect_incident(self, owner_id, incident_id):
        return self.incident

    def advance_incident(self, owner_id, incident_id, stage, evidence_id):
        self.incident = replace(
            self.incident, stage=stage, revision=self.incident.revision + 1,
        )
        return self.incident

    def reviews_for_task(self, owner_id, task_id):
        return review_schema_values()[:1]

    def review_evidence_for_task(self, owner_id, task_id):
        values = review_schema_values()
        return values[1:3] + values[4:]

    def documentation_for_task(self, owner_id, task_id):
        return documentation_schema_values()

    def runtime_diagnostic_requests(self, owner_id, task_id):
        return diagnostics_schema_values()[:1]

    def runtime_diagnostic_receipts(self, owner_id, task_id):
        return diagnostics_schema_values()[1:]

    def database_plans(self, owner_id, task_id):
        return database_engineering_schema_values()[1:2]

    def database_results(self, owner_id, task_id):
        _target, plan, _permit, backup, verification = (
            database_engineering_schema_values()
        )
        return (SimpleNamespace(
            plan=plan, backup=backup, verification=verification,
        ),)

    def database_postapply_receipts(self, owner_id, task_id):
        return database_postapply_schema_values()

    def _view(self, task_id):
        return {"task_id": task_id, "stage": self.stage, "revision": 0,
                "intent": "Implement task", "workspace_roots": ["/workspace"],
                "acceptance_policy_id": "acceptance-1",
                "task_graph_evidence_id": None, "candidate_id": None,
                "diff_checkpoint_id": None, "test_receipt_ids": [],
                "runtime_diagnostic_receipt_ids": [],
                "database_receipt_ids": [],
                "database_postapply_receipt_ids": [],
                "integration_environment_receipt_ids": [],
                "integration_environment_postapply_receipt_ids": [],
                "dependency_receipt_ids": [], "design_preview_receipt_ids": [],
                "rollback_receipt_ids": [], "git_receipt_ids": [],
                "publication_approval_id": None, "budget": {}}


def _session(base):
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
    )
    request = urllib.request.Request(
        base + "/api/v1/session", data=b"{}", method="POST",
        headers={"Authorization": "Bearer " + "x" * 32, "Origin": base},
    )
    return opener, json.loads(opener.open(request).read())["csrf_token"]


def _get(opener, url):
    return json.loads(opener.open(url).read())


def _post(opener, url, csrf, body):
    request = urllib.request.Request(
        url, data=json.dumps(body).encode(), method="POST",
        headers={"Content-Type": "application/json",
                 "Origin": url.rsplit("/api/", 1)[0], "X-CSRF-Token": csrf},
    )
    return json.loads(opener.open(request).read())


if __name__ == "__main__":
    unittest.main()
