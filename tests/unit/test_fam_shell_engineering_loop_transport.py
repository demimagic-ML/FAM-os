import os
import base64
import hashlib
import tempfile
import threading
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from fam_os.adapters.shell import (
    ShellRequestDispatcher,
    UnixShellClientConfiguration,
    UnixShellCoreClient,
    UnixShellServer,
    UnixShellServerConfiguration,
)
from fam_os.applications.transport.auth import PeerAuthorizationPolicy
from fam_os.core.engineering import (
    CandidateArtifact, CandidateContentKind, CandidateOperation,
    CandidateOperationKind, EngineeringIncidentStage, EngineeringLoopBudget,
)
from fam_os.shell import (
    ShellEngineeringLoopMutation,
    ShellEngineeringLoopOperation,
    ShellEngineeringLoopQuery,
    ShellEngineeringLoopStartRequest,
    ShellEngineeringCandidateEditRequest,
    ShellEngineeringCandidateVerificationRequest,
    ShellEngineeringCandidateReverificationRequest,
    ShellEngineeringChangesetApplyRequest,
    ShellEngineeringChangesetPreviewRequest,
    ShellEngineeringIncidentAdvanceRequest,
    ShellEngineeringPublicationRequest,
)
from tests.contract.schema_candidate_edit_fixtures import candidate_edit_schema_values
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


class ShellEngineeringLoopTransportTests(unittest.TestCase):
    def test_owner_uid_endpoint_starts_queries_and_resumes_lifecycle(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            os.chmod(root, 0o700)
            server = UnixShellServer(
                UnixShellServerConfiguration(root / "shell.sock"),
                PeerAuthorizationPolicy(os.geteuid()),
                ShellRequestDispatcher(_UnusedCore(), engineering_loop=_Api()),
            )
            server.open()
            self.addCleanup(server.close)
            client = UnixShellCoreClient(
                UnixShellClientConfiguration(root / "shell.sock"),
            )
            started = _serve(server, lambda: client.engineering_loop_start(
                ShellEngineeringLoopStartRequest(
                    "start-1", "owner-1", task_definition_schema_values()[0],
                    EngineeringLoopBudget(10, 10, 10, 10, 10, 10), True,
                )
            ))
            self.assertEqual("task-1", started.view.task_id)
            resumed = _serve(server, lambda: client.engineering_loop_mutation(
                ShellEngineeringLoopMutation(
                    "resume-1", ShellEngineeringLoopOperation.RESUME,
                    "owner-1", "task-1",
                )
            ))
            self.assertEqual("requested", resumed.view.stage)
            prepared = _serve(server, lambda: client.engineering_loop_mutation(
                ShellEngineeringLoopMutation(
                    "prepare-1", ShellEngineeringLoopOperation.PREPARE,
                    "owner-1", "task-1",
                )
            ))
            self.assertEqual("candidate_ready", prepared.view.stage)
            content = b"generated = True\n"
            artifact = CandidateArtifact(
                "artifact-shell-1", CandidateContentKind.TEXT, "text/x-python",
                hashlib.sha256(content).hexdigest(), len(content), "owner-request",
            )
            edited = _serve(server, lambda: client.engineering_candidate_edit(
                ShellEngineeringCandidateEditRequest(
                    "edit-request-1", "owner-1", "task-1", "edit-1",
                    "session-1", "principal-1",
                    CandidateOperation(
                        "operation-shell-1", CandidateOperationKind.CREATE_FILE,
                        "src/generated.py", artifact_id=artifact.artifact_id,
                    ),
                    artifact, base64.b64encode(content).decode(), True,
                )
            ))
            self.assertEqual("edit-1", edited.edit.edit_id)
            edits = _serve(server, lambda: client.engineering_loop_query(
                ShellEngineeringLoopQuery(
                    "edits-1", ShellEngineeringLoopOperation.EDITS,
                    "owner-1", "task-1",
                )
            ))
            self.assertEqual(1, len(edits.edits))
            verified = _serve(server, lambda: client.engineering_candidate_verify(
                ShellEngineeringCandidateVerificationRequest(
                    "verify-request-1", "owner-1", "task-1", "verification-1",
                    "session-1", "principal-1", "python3",
                    "engineering.python.test", "1.0.0", True,
                )
            ))
            self.assertEqual("verification-1", verified.verification.verification_id)
            verifications = _serve(server, lambda: client.engineering_loop_query(
                ShellEngineeringLoopQuery(
                    "verifications-1", ShellEngineeringLoopOperation.VERIFICATIONS,
                    "owner-1", "task-1",
                )
            ))
            self.assertEqual(1, len(verifications.verifications))
            previewed = _serve(server, lambda: client.engineering_changeset_preview(
                ShellEngineeringChangesetPreviewRequest(
                    "preview-1", "owner-1", "task-1", "transaction-1", True,
                )
            ))
            self.assertEqual("transaction-1", previewed.changeset.changeset_id)
            changeset_fixture = candidate_changeset_schema_values()[0]
            applied = _serve(server, lambda: client.engineering_changeset_apply(
                ShellEngineeringChangesetApplyRequest(
                    "apply-1", "owner-1", "task-1", "transaction-1",
                    changeset_fixture.decision, "session-1", "principal-1", True,
                )
            ))
            self.assertEqual("applied", applied.changeset.status.value)
            reverified = _serve(server, lambda: client.engineering_candidate_reverify(
                ShellEngineeringCandidateReverificationRequest(
                    "reverify-request-1", "owner-1", "task-1", "verification-2",
                    "session-1", "principal-1", "python3",
                    "engineering.python.test", "1.0.0", True,
                )
            ))
            self.assertEqual("verification-1", reverified.verification.verification_id)
            changesets = _serve(server, lambda: client.engineering_loop_query(
                ShellEngineeringLoopQuery(
                    "changesets-1", ShellEngineeringLoopOperation.CHANGESETS,
                    "owner-1", "task-1",
                )
            ))
            self.assertEqual(1, len(changesets.changesets))
            approval = git_schema_values()[3]
            published = _serve(server, lambda: client.engineering_publication(
                ShellEngineeringPublicationRequest(
                    "publication-1", "owner-1", approval.task_id,
                    approval, True,
                )
            ))
            self.assertEqual(approval.approval_id, published.publication.approval_id)
            self.assertEqual(approval.proposed_new_object_id,
                             published.publication.published_new_object_id)
            incidents = _serve(server, lambda: client.engineering_loop_query(
                ShellEngineeringLoopQuery(
                    "incidents-1", ShellEngineeringLoopOperation.INCIDENTS,
                    "owner-1", "task-1",
                )
            ))
            self.assertEqual("incident-1", incidents.incidents[0].incident_id)
            self.assertEqual(
                "preservation-1", incidents.incident_evidence[0].receipt_id,
            )
            advanced = _serve(server, lambda: client.engineering_incident_advance(
                ShellEngineeringIncidentAdvanceRequest(
                    "incident-advance-1", "owner-1", "task-1", "incident-1",
                    EngineeringIncidentStage.REMEDIATION_PROPOSED,
                    "changeset-remediation-1", True,
                )
            ))
            self.assertEqual(
                EngineeringIncidentStage.REMEDIATION_PROPOSED,
                advanced.incident.stage,
            )
            reviews = _serve(server, lambda: client.engineering_loop_query(
                ShellEngineeringLoopQuery(
                    "reviews-1", ShellEngineeringLoopOperation.REVIEWS,
                    "owner-1", "task-1",
                )
            ))
            self.assertEqual("review-1", reviews.reviews[0].checkpoint_id)
            self.assertEqual(
                "selection-1", reviews.review_evidence[1].selection_id,
            )
            documentation = _serve(server, lambda: client.engineering_loop_query(
                ShellEngineeringLoopQuery(
                    "documentation-1",
                    ShellEngineeringLoopOperation.DOCUMENTATION,
                    "owner-1", "task-1",
                )
            ))
            self.assertEqual(6, len(documentation.documentation))
            diagnostics = _serve(server, lambda: client.engineering_loop_query(
                ShellEngineeringLoopQuery(
                    "runtime-diagnostics-1",
                    ShellEngineeringLoopOperation.RUNTIME_DIAGNOSTICS,
                    "owner-1", "task-1",
                )
            ))
            self.assertEqual(
                "diagnostic-request-1",
                diagnostics.runtime_diagnostic_requests[0].request_id,
            )
            self.assertEqual(
                "diagnostic-receipt-1",
                diagnostics.runtime_diagnostics[0].receipt_id,
            )
            database = _serve(server, lambda: client.engineering_loop_query(
                ShellEngineeringLoopQuery(
                    "database-1", ShellEngineeringLoopOperation.DATABASE,
                    "owner-1", "task-1",
                )
            ))
            self.assertEqual(
                "database-plan-1", database.database_plans[0].plan_id,
            )
            self.assertEqual(
                "database-receipt-1",
                database.database_verifications[0].receipt_id,
            )
            self.assertTrue(database.database_postapply[0].passed)
            listed = _serve(server, lambda: client.engineering_loop_query(
                ShellEngineeringLoopQuery(
                    "list-1", ShellEngineeringLoopOperation.LIST, "owner-1",
                )
            ))
            self.assertEqual(1, len(listed.views))


class _Api:
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
        from tests.contract.schema_candidate_verification_fixtures import (
            candidate_verification_schema_values,
        )
        return candidate_verification_schema_values()[0]

    def reverify_candidate(self, owner_id, task_id, **kwargs):
        from tests.contract.schema_candidate_verification_fixtures import (
            candidate_verification_schema_values,
        )
        return candidate_verification_schema_values()[0]

    def candidate_verifications(self, owner_id, task_id):
        from tests.contract.schema_candidate_verification_fixtures import (
            candidate_verification_schema_values,
        )
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
        _target, plan, _permit, backup, receipt = (
            database_engineering_schema_values()
        )
        return (SimpleNamespace(
            plan=plan, backup=backup, verification=receipt,
        ),)

    def database_postapply_receipts(self, owner_id, task_id):
        return database_postapply_schema_values()

    def _view(self, task_id):
        return {
            "task_id": task_id, "stage": self.stage, "revision": 0,
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
            "publication_approval_id": None,
            "budget": {"tokens": 0, "wall_seconds": 0, "commands": 0,
                       "network_bytes": 0, "files": 0, "storage_bytes": 0},
        }


class _UnusedCore:
    pass


def _serve(server, operation):
    results, failures = [], []
    thread = threading.Thread(target=lambda: _capture(operation, results, failures))
    thread.start()
    server.serve_once()
    thread.join(timeout=5)
    if failures:
        raise failures[0]
    return results[0]


def _capture(operation, results, failures):
    try:
        results.append(operation())
    except Exception as error:
        failures.append(error)


if __name__ == "__main__":
    unittest.main()
