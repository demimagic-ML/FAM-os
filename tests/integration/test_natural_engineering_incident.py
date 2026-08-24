import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from fam_os.adapters.filesystem import (
    BoundedCandidateContextReader, BoundedFilesystemRepositoryObserver,
)
from fam_os.adapters.git import LocalGitAdapter
from fam_os.adapters.sqlite import (
    SQLiteCandidateChangesetStore, SQLiteCandidateEditStore,
    SQLiteCandidateGenerationStore, SQLiteCandidateVerificationStore,
    SQLiteEngineeringIncidentStore, SQLiteEngineeringLoopStore,
    SQLiteEngineeringPreparationStore, SQLiteNaturalEngineeringProposalStore,
    SQLiteLocalGitDeliveryStore, SQLiteEngineeringDocumentationStore,
)
from fam_os.core.engineering import (
    CandidateGenerationService, CandidateVerificationService,
    EngineeringIncidentService, EngineeringIncidentStage,
    LocalGitDeliveryService, DocumentationGenerationService,
)
from fam_os.adapters.documentation import DeterministicDocumentationGenerator
from fam_os.product.engineering_loop_api import ProductEngineeringLoopApi
from fam_os.product.natural_engineering_api import ProductNaturalEngineeringApi
from fam_os.product.natural_engineering_execution import (
    NaturalEngineeringExecutionCoordinator,
)
from fam_os.product.natural_engineering_documentation import (
    NaturalEngineeringDocumentationCoordinator,
)
from fam_os.core.ports.inference import InferenceResponse
from fam_os.telemetry.contracts import InferenceMetrics
from tests.integration.test_natural_engineering_checkpoint import (
    _Authentication, _Authority, _Recipes, _Runner, _Runtime,
    _documentation_recipes,
)


class NaturalEngineeringIncidentIntegrationTests(unittest.TestCase):
    def test_failed_candidate_is_repaired_squashed_monitored_and_delivered(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "project"
            workspace.mkdir()
            (workspace / "app.py").write_text("VALUE = 1\n")
            (workspace / "tests").mkdir()
            (workspace / "tests/test_app.py").write_text(
                "from app import VALUE\n\ndef test_value():\n    assert VALUE == 1\n"
            )
            _initialize_repository(workspace)
            authority = _Authority()
            recipes = _Recipes()
            documentation_recipes = _documentation_recipes()
            verification_store = SQLiteCandidateVerificationStore(
                root / "verifications.sqlite3",
            )
            loop = ProductEngineeringLoopApi(
                "owner-1", authority,
                SQLiteEngineeringLoopStore(root / "loop.sqlite3"),
                root / "candidates",
                SQLiteEngineeringPreparationStore(root / "preparation.sqlite3"),
                authority, SQLiteCandidateEditStore(root / "edits.sqlite3"),
                CandidateVerificationService(
                    authority, recipes, _Runner(), _PassAfterRepairVerifier(),
                    verification_store,
                ),
                verification_store,
                SQLiteCandidateChangesetStore(root / "changesets.sqlite3"),
                recipes,
                LocalGitDeliveryService(
                    authority, LocalGitAdapter(),
                    SQLiteLocalGitDeliveryStore(root / "git-delivery.sqlite3"),
                ),
                incident_service=EngineeringIncidentService(
                    SQLiteEngineeringIncidentStore(root / "incidents.sqlite3"),
                ),
                documentation_store=SQLiteEngineeringDocumentationStore(
                    root / "documentation.sqlite3",
                ),
                documentation_recipes=documentation_recipes,
            )
            runtime = _RepairRuntime()
            generation = CandidateGenerationService(
                runtime, "model:1",
                SQLiteCandidateGenerationStore(root / "generation.sqlite3"),
            )
            api = ProductNaturalEngineeringApi(
                "owner-1",
                SQLiteNaturalEngineeringProposalStore(root / "proposals.sqlite3"),
                _Authentication(), authority, loop,
                BoundedFilesystemRepositoryObserver(),
                executor=NaturalEngineeringExecutionCoordinator(
                    loop, BoundedCandidateContextReader(), generation,
                    NaturalEngineeringDocumentationCoordinator(
                        loop, DocumentationGenerationService(
                            documentation_recipes,
                            DeterministicDocumentationGenerator(),
                        ),
                    ),
                ),
                identifier=lambda: "repaired-incident",
            )
            proposal = api.propose(
                "owner-1", "Replace the Python API value with 3 and run tests.",
                str(workspace),
            )
            prepared = api.activate(
                "owner-1", proposal["proposal_id"], "console-session-1",
                confirmed=True,
            )["engineering_task"]

            self.assertEqual("changeset_approval_required", prepared["outcome"])
            self.assertEqual(1, prepared["repair_count"])
            self.assertEqual(1, len(prepared["generated_documentation"]))
            self.assertEqual(1, len(prepared["requirement_traces"]))
            self.assertEqual(
                "recovery_monitored", prepared["incident"]["payload"]["stage"],
            )
            self.assertEqual(5, len(prepared["incident_evidence"]))
            self.assertEqual(4, len(prepared["candidate_edits"]))
            self.assertEqual(1, len(prepared["candidate_verifications"]))
            changeset = prepared["changeset"]["payload"]
            self.assertEqual(8, len(changeset["operations"]))
            self.assertEqual(1, sum(
                item["path"] == "app.py" for item in changeset["operations"]
            ))
            documentation = loop.documentation_for_task(
                "owner-1", prepared["task_id"],
            )
            self.assertEqual(2, sum(
                type(item).__name__ == "GeneratedDocumentationReceipt"
                for item in documentation
            ))
            self.assertEqual(2, sum(
                type(item).__name__ == "DocumentationGovernanceBinding"
                for item in documentation
            ))
            self.assertEqual(1, sum(
                type(item).__name__ == "RequirementTraceabilityRecord"
                for item in documentation
            ))
            self.assertEqual(1, sum(
                type(item).__name__ == "DocumentationRequirementSelection"
                for item in documentation
            ))
            trace = next(
                item for item in documentation
                if type(item).__name__ == "RequirementTraceabilityRecord"
            )
            self.assertEqual("satisfied", trace.status.value)
            self.assertEqual(("tests/test_app.py",), trace.test_paths)
            candidate = loop.preparation(
                "owner-1", prepared["task_id"],
            ).candidate
            requirement_text = (
                Path(candidate.candidate_workspace)
                / "docs/generated/FAM_REQUIREMENTS.md"
            ).read_text()
            self.assertNotIn(
                "Replace the Python API value", requirement_text,
            )
            self.assertIn("Task digest:", requirement_text)
            self.assertEqual(
                "VALUE = 3\n",
                (Path(candidate.candidate_workspace) / "app.py").read_text(),
            )
            self.assertIn(
                "untrusted_verifier_feedback", runtime.requests[1].messages[-1].content,
            )
            self.assertNotIn(
                "credential-value", runtime.requests[1].messages[-1].content,
            )
            self.assertIn(
                "REDACTED_DIAGNOSTIC", runtime.requests[1].messages[-1].content,
            )

            completed = api.approve_changeset(
                "owner-1", proposal["proposal_id"], changeset["changeset_id"],
                "console-session-1", confirmed=True,
            )["engineering_task"]
            self.assertEqual("local_commit_completed", completed["outcome"])
            self.assertEqual("closed", completed["incident"]["payload"]["stage"])
            self.assertEqual(8, len(completed["incident_evidence"]))
            recovery = tuple(
                item["payload"] for item in completed["incident_evidence"]
                if item["payload"]["kind"] == "recovery_observation"
            )
            self.assertEqual(2, len(recovery))
            self.assertNotEqual(
                recovery[0]["conclusion_code"], recovery[1]["conclusion_code"],
            )
            self.assertEqual("VALUE = 3\n", (workspace / "app.py").read_text())
            postapply_documentation = loop.documentation_for_task(
                "owner-1", prepared["task_id"],
            )
            reports = tuple(
                item for item in postapply_documentation
                if type(item).__name__ == "DocumentationStalenessReport"
            )
            self.assertEqual(2, len(reports))
            self.assertEqual({False, True}, {item.stale for item in reports})
            self.assertEqual("2", _git(workspace, "rev-list", "--count", "HEAD"))
            self.assertEqual(4, loop.inspect(
                "owner-1", prepared["task_id"],
            )["budget"]["commands"])
            api.close()
            loop.close()

    def test_failed_signed_verification_attaches_and_persists_exact_incident(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "project"
            workspace.mkdir()
            (workspace / "app.py").write_text("VALUE = 1\n")
            _initialize_repository(workspace)
            authority = _Authority()
            recipes = _Recipes()
            verification_store = SQLiteCandidateVerificationStore(
                root / "verifications.sqlite3",
            )
            incident_path = root / "incidents.sqlite3"
            loop = ProductEngineeringLoopApi(
                "owner-1", authority,
                SQLiteEngineeringLoopStore(root / "loop.sqlite3"),
                root / "candidates",
                SQLiteEngineeringPreparationStore(root / "preparation.sqlite3"),
                authority, SQLiteCandidateEditStore(root / "edits.sqlite3"),
                CandidateVerificationService(
                    authority, recipes, _Runner(), _FailingVerifier(),
                    verification_store,
                ),
                verification_store,
                SQLiteCandidateChangesetStore(root / "changesets.sqlite3"),
                recipes,
                incident_service=EngineeringIncidentService(
                    SQLiteEngineeringIncidentStore(incident_path),
                ),
            )
            generation = CandidateGenerationService(
                _Runtime(), "model:1",
                SQLiteCandidateGenerationStore(root / "generation.sqlite3"),
            )
            api = ProductNaturalEngineeringApi(
                "owner-1",
                SQLiteNaturalEngineeringProposalStore(root / "proposals.sqlite3"),
                _Authentication(), authority, loop,
                BoundedFilesystemRepositoryObserver(),
                executor=NaturalEngineeringExecutionCoordinator(
                    loop, BoundedCandidateContextReader(), generation,
                ),
                identifier=lambda: "incident",
            )
            proposal = api.propose(
                "owner-1", "Replace the Python value with 2 and run tests.",
                str(workspace),
            )
            result = api.activate(
                "owner-1", proposal["proposal_id"], "console-session-1",
                confirmed=True,
            )

            task = result["engineering_task"]
            self.assertEqual("verification_failed", task["outcome"])
            incident_document = task["incident"]["payload"]
            self.assertEqual("diagnosed", incident_document["stage"])
            self.assertEqual(
                ["verification-generation-engineering-incident-1-0"],
                incident_document["symptom_evidence_ids"],
            )
            self.assertEqual(1, len(incident_document["preservation_receipt_ids"]))
            self.assertEqual(1, len(incident_document["diagnosis_receipt_ids"]))
            progress = api.progress("owner-1", proposal["proposal_id"])
            self.assertEqual(
                incident_document["incident_id"],
                progress["engineering_task"]["incident"]["payload"]["incident_id"],
            )
            self.assertEqual(1, len(progress["engineering_task"]["incidents"]))
            self.assertEqual(
                2, len(progress["engineering_task"]["incident_evidence"]),
            )
            incident_id = incident_document["incident_id"]
            with self.assertRaises(KeyError):
                loop.advance_incident(
                    "owner-1", incident_id,
                    EngineeringIncidentStage.REMEDIATION_PROPOSED,
                    "fabricated-evidence",
                )
            with self.assertRaises(PermissionError):
                loop.advance_incident(
                    "owner-1", incident_id,
                    EngineeringIncidentStage.REMEDIATION_PROPOSED,
                    incident_document["diagnosis_receipt_ids"][0],
                )
            api.close()
            loop.close()

            restarted_store = SQLiteEngineeringIncidentStore(incident_path)
            restarted = EngineeringIncidentService(restarted_store)
            persisted = restarted.inspect(incident_id)
            self.assertEqual(EngineeringIncidentStage.DIAGNOSED, persisted.stage)
            self.assertEqual(
                ("verification-generation-engineering-incident-1-0",),
                persisted.symptom_evidence_ids,
            )
            self.assertEqual(2, len(restarted.receipts(incident_id)))
            restarted_store.close()

    def test_postapply_failure_offers_exact_rollback_and_closes_incident(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "project"
            workspace.mkdir()
            (workspace / "app.py").write_text("VALUE = 1\n")
            _initialize_repository(workspace)
            authority = _Authority()
            recipes = _Recipes()
            verification_store = SQLiteCandidateVerificationStore(
                root / "verifications.sqlite3",
            )
            incident_path = root / "incidents.sqlite3"
            loop = ProductEngineeringLoopApi(
                "owner-1", authority,
                SQLiteEngineeringLoopStore(root / "loop.sqlite3"),
                root / "candidates",
                SQLiteEngineeringPreparationStore(root / "preparation.sqlite3"),
                authority, SQLiteCandidateEditStore(root / "edits.sqlite3"),
                CandidateVerificationService(
                    authority, recipes, _Runner(), _PassThenFailVerifier(),
                    verification_store,
                ),
                verification_store,
                SQLiteCandidateChangesetStore(root / "changesets.sqlite3"),
                recipes,
                LocalGitDeliveryService(
                    authority, LocalGitAdapter(),
                    SQLiteLocalGitDeliveryStore(root / "git-delivery.sqlite3"),
                ),
                incident_service=EngineeringIncidentService(
                    SQLiteEngineeringIncidentStore(incident_path),
                ),
            )
            generation = CandidateGenerationService(
                _Runtime(), "model:1",
                SQLiteCandidateGenerationStore(root / "generation.sqlite3"),
            )
            api = ProductNaturalEngineeringApi(
                "owner-1",
                SQLiteNaturalEngineeringProposalStore(root / "proposals.sqlite3"),
                _Authentication(), authority, loop,
                BoundedFilesystemRepositoryObserver(),
                executor=NaturalEngineeringExecutionCoordinator(
                    loop, BoundedCandidateContextReader(), generation,
                ),
                identifier=lambda: "postapply-incident",
            )
            proposal = api.propose(
                "owner-1", "Replace the Python value with 2 and run tests.",
                str(workspace),
            )
            prepared = api.activate(
                "owner-1", proposal["proposal_id"], "console-session-1",
                confirmed=True,
            )["engineering_task"]
            failed = api.approve_changeset(
                "owner-1", proposal["proposal_id"],
                prepared["changeset"]["payload"]["changeset_id"],
                "console-session-1", confirmed=True,
            )["engineering_task"]

            self.assertEqual("postapply_verification_failed", failed["outcome"])
            self.assertEqual("applied", failed["stage"])
            self.assertEqual("VALUE = 2\n", (workspace / "app.py").read_text())
            self.assertEqual(
                "remediation_proposed", failed["incident"]["payload"]["stage"],
            )
            self.assertIn("rollback_checkpoint", failed)
            self.assertIn(
                "Do not create or rewrite a Git commit.",
                failed["rollback_checkpoint"]["consequences"],
            )
            self.assertEqual("1", _git(workspace, "rev-list", "--count", "HEAD"))
            resumed = api.progress("owner-1", proposal["proposal_id"])[
                "engineering_task"
            ]
            self.assertEqual("postapply_verification_failed", resumed["outcome"])
            self.assertEqual(
                failed["rollback_checkpoint"]["approval_sha256"],
                resumed["rollback_checkpoint"]["approval_sha256"],
            )
            self.assertEqual(
                "remediation_proposed", resumed["incident"]["payload"]["stage"],
            )

            rolled_back = api.rollback(
                "owner-1", proposal["proposal_id"],
                failed["rollback_checkpoint"]["rollback_id"],
                "console-session-1", confirmed=True,
            )["engineering_task"]
            self.assertEqual("rollback_completed", rolled_back["outcome"])
            self.assertEqual("rolled_back", rolled_back["stage"])
            self.assertNotIn("git_rollback_delivery", rolled_back)
            self.assertEqual("VALUE = 1\n", (workspace / "app.py").read_text())
            self.assertEqual("1", _git(workspace, "rev-list", "--count", "HEAD"))
            self.assertEqual("closed", rolled_back["incident"]["payload"]["stage"])
            self.assertEqual(6, len(rolled_back["incident_evidence"]))
            incident_id = rolled_back["incident"]["payload"]["incident_id"]
            retried = api.rollback(
                "owner-1", proposal["proposal_id"],
                failed["rollback_checkpoint"]["rollback_id"],
                "console-session-1", confirmed=True,
            )["engineering_task"]
            self.assertEqual("rollback_completed", retried["outcome"])
            self.assertEqual("closed", retried["incident"]["payload"]["stage"])
            self.assertEqual(6, len(retried["incident_evidence"]))
            self.assertEqual("1", _git(workspace, "rev-list", "--count", "HEAD"))

            api.close()
            loop.close()
            restarted_store = SQLiteEngineeringIncidentStore(incident_path)
            restarted = EngineeringIncidentService(restarted_store)
            self.assertEqual(
                EngineeringIncidentStage.CLOSED,
                restarted.inspect(incident_id).stage,
            )
            self.assertEqual(6, len(restarted.receipts(incident_id)))
            restarted_store.close()


class _FailingVerifier:
    def verify(self, receipt, recipe_version):
        return type("Report", (), {
            "passed": False,
            "verifier_ids": ("verifier-natural-failure-1",),
            "reason": "fixture verification failure",
        })()


class _PassThenFailVerifier:
    def __init__(self):
        self.calls = 0

    def verify(self, receipt, recipe_version):
        self.calls += 1
        return type("Report", (), {
            "passed": self.calls == 1,
            "verifier_ids": (f"verifier-natural-{self.calls}",),
            "reason": "passed" if self.calls == 1 else "post-apply failure",
        })()


class _PassAfterRepairVerifier:
    def __init__(self):
        self.calls = 0

    def verify(self, receipt, recipe_version):
        self.calls += 1
        return type("Report", (), {
            "passed": self.calls > 1,
            "verifier_ids": (f"verifier-repair-{self.calls}",),
            "reason": (
                "fixture test failed at /home/owner/private/app.py "
                "token=credential-value"
                if self.calls == 1 else "passed"
            ),
        })()


class _RepairRuntime:
    def __init__(self):
        self.requests = []

    def chat(self, request):
        self.requests.append(request)
        value = 2 if len(self.requests) == 1 else 3
        return InferenceResponse(
            json.dumps({
                "contract_version": "fam.core.engineering/v1alpha1",
                "summary": "Replace app value",
                "operations": [
                    {
                        "kind": "replace_file", "path": "app.py",
                        "content": f"VALUE = {value}\n", "source_path": None,
                        "media_type": "text/x-python",
                    },
                    {
                        "kind": "replace_file", "path": "tests/test_app.py",
                        "content": (
                            "from app import VALUE\n\ndef test_value():\n"
                            f"    assert VALUE == {value}\n"
                        ),
                        "source_path": None, "media_type": "text/x-python",
                    },
                ],
            }),
            InferenceMetrics("model:1", 0.1, 0.0, 20, 20),
        )


def _initialize_repository(workspace: Path) -> None:
    import subprocess

    subprocess.run(("git", "init", "-q", str(workspace)), check=True)
    subprocess.run(("git", "-C", str(workspace), "add", "."), check=True)
    subprocess.run((
        "git", "-C", str(workspace), "-c", "user.name=Test", "-c",
        "user.email=test@example.invalid", "commit", "-q", "-m", "initial",
    ), check=True)


def _git(workspace: Path, *args: str) -> str:
    return subprocess.run(
        ("git", "-C", str(workspace), *args), check=True,
        capture_output=True, text=True,
    ).stdout.strip()


if __name__ == "__main__":
    unittest.main()
