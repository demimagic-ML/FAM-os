import hashlib
import json
import subprocess
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from fam_os.adapters.crypto.engineering_recipes import (
    Ed25519RecipeSignatureVerifier, sign_recipe_specification,
)
from fam_os.adapters.filesystem import (
    BoundedCandidateContextReader, BoundedFilesystemRepositoryObserver,
)
from fam_os.adapters.git import LocalGitAdapter
from fam_os.adapters.sqlite import (
    SQLiteCandidateChangesetStore, SQLiteCandidateEditStore,
    SQLiteCandidateGenerationStore, SQLiteCandidateVerificationStore,
    SQLiteEngineeringLoopStore, SQLiteEngineeringPreparationStore,
    SQLiteLocalGitDeliveryStore, SQLiteNaturalEngineeringProposalStore,
    SQLiteRuntimeDiagnosticStore,
)
from fam_os.core.engineering import (
    CandidateGenerationService, CandidateVerificationService,
    EngineeringAuthorizationDecision, EngineeringEcosystem,
    EngineeringToolReceipt, LocalGitDeliveryService,
    RuntimeDiagnosticPhase, RuntimeDiagnosticReceipt,
    RuntimeDiagnosticRecipePolicy, RuntimeDiagnosticService,
    RuntimeDiagnosticStatus, RuntimeDiagnosticArtifact,
    RuntimePerformanceMode, ToolQualificationStatus, ToolRecipePurpose,
)
from fam_os.core.engineering.execution_policy import SignedToolRecipeCatalog
from fam_os.core.engineering.production_recipes import (
    diagnostic_recipe_specifications,
)
from fam_os.core.ports.inference import InferenceResponse
from fam_os.product.engineering_loop_api import ProductEngineeringLoopApi
from fam_os.product.natural_engineering_api import ProductNaturalEngineeringApi
from fam_os.product.natural_engineering_execution import (
    NaturalEngineeringExecutionCoordinator,
)
from fam_os.telemetry.contracts import InferenceMetrics


class NaturalRuntimeDiagnosticIntegrationTests(unittest.TestCase):
    def test_performance_regression_captures_pristine_exact_baseline_before_edit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = _workspace(root)
            api, loop = _system(root, workspace)
            proposal = api.propose(
                "owner-1",
                "Replace the Python API value with 2 and compare performance of app.py with no more than 10% regression.",
                str(workspace),
            )
            task = api.activate(
                "owner-1", proposal["proposal_id"], "console-session-1",
                confirmed=True,
            )["engineering_task"]

            self.assertEqual("changeset_approval_required", task["outcome"])
            requests = loop.runtime_diagnostic_requests(
                "owner-1", task["task_id"],
            )
            baseline = next(
                item for item in requests
                if item.phase is RuntimeDiagnosticPhase.BASELINE
            )
            comparison = next(
                item for item in requests
                if item.phase is RuntimeDiagnosticPhase.CANDIDATE
            )
            receipts = {
                item.request_id: item for item in loop.runtime_diagnostic_receipts(
                    "owner-1", task["task_id"],
                )
            }
            self.assertEqual(
                receipts[baseline.request_id].baseline_artifact_sha256,
                comparison.baseline_artifact_sha256,
            )
            self.assertEqual(100_000, comparison.maximum_regression_ppm)
            self.assertEqual(3, len(
                task["changeset"]["payload"]["preview"][
                    "verification_evidence_ids"
                ]
            ))
            completed = api.approve_changeset(
                "owner-1", proposal["proposal_id"],
                task["changeset"]["payload"]["changeset_id"],
                "console-session-1", confirmed=True,
            )["engineering_task"]
            self.assertEqual("local_commit_completed", completed["outcome"])
            postapply = next(
                item for item in loop.runtime_diagnostic_requests(
                    "owner-1", task["task_id"],
                ) if item.phase is RuntimeDiagnosticPhase.POSTAPPLY
            )
            self.assertEqual(
                comparison.baseline_artifact_sha256,
                postapply.baseline_artifact_sha256,
            )
            api.close()
            loop.close()

    def test_modify_diagnose_checkpoint_and_postapply_reverification_are_one_lifecycle(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = _workspace(root)
            api, loop = _system(root, workspace)
            proposal = api.propose(
                "owner-1",
                "Replace the Python API value with 2 and profile CPU usage of app.py.",
                str(workspace),
            )
            activated = api.activate(
                "owner-1", proposal["proposal_id"], "console-session-1",
                confirmed=True,
            )

            task = activated["engineering_task"]
            self.assertEqual("changeset_approval_required", task["outcome"])
            self.assertEqual(1, len(task["runtime_diagnostics"]))
            preview_evidence = task["changeset"]["payload"]["preview"][
                "verification_evidence_ids"
            ]
            self.assertEqual(2, len(preview_evidence))
            receipt_id = task["runtime_diagnostics"][0]["payload"]["receipt_id"]
            self.assertIn(receipt_id, preview_evidence)
            self.assertEqual("VALUE = 1\n", (workspace / "app.py").read_text())

            completed = api.approve_changeset(
                "owner-1", proposal["proposal_id"],
                task["changeset"]["payload"]["changeset_id"],
                "console-session-1", confirmed=True,
            )["engineering_task"]

            self.assertEqual("local_commit_completed", completed["outcome"])
            self.assertEqual(1, len(completed["postapply_runtime_diagnostics"]))
            requests = loop.runtime_diagnostic_requests(
                "owner-1", task["task_id"],
            )
            self.assertEqual(
                {RuntimeDiagnosticPhase.CANDIDATE, RuntimeDiagnosticPhase.POSTAPPLY},
                {item.phase for item in requests},
            )
            self.assertEqual("VALUE = 2\n", (workspace / "app.py").read_text())
            api.close()
            loop.close()

    def test_diagnostic_only_natural_request_runs_without_generation_or_owner_mutation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = _workspace(root)
            api, loop = _system(root, workspace)
            proposal = api.propose(
                "owner-1", "Profile CPU usage of app.py.", str(workspace),
            )
            result = api.activate(
                "owner-1", proposal["proposal_id"], "console-session-1",
                confirmed=True,
            )["engineering_task"]

            self.assertEqual("runtime_diagnostics_completed", result["outcome"])
            self.assertEqual("candidate_ready", result["stage"])
            self.assertEqual(1, len(result["runtime_diagnostics"]))
            self.assertEqual("VALUE = 1\n", (workspace / "app.py").read_text())
            self.assertEqual(
                "runtime_diagnostics_completed",
                api.progress("owner-1", proposal["proposal_id"])[
                    "engineering_task"
                ]["outcome"],
            )
            api.close()
            loop.close()


def _system(root, workspace):
    authority = _Authority()
    recipes = _Recipes()
    verification_store = SQLiteCandidateVerificationStore(
        root / "verifications.sqlite3",
    )
    diagnostic_store = SQLiteRuntimeDiagnosticStore(
        root / "runtime-diagnostics.sqlite3",
    )
    loop = ProductEngineeringLoopApi(
        "owner-1", authority,
        SQLiteEngineeringLoopStore(root / "loop.sqlite3"),
        root / "candidates",
        SQLiteEngineeringPreparationStore(root / "preparation.sqlite3"),
        authorizer=authority,
        edits=SQLiteCandidateEditStore(root / "edits.sqlite3"),
        verification_service=CandidateVerificationService(
            authority, recipes, _VerificationRunner(), _Verifier(),
            verification_store,
        ),
        verifications=verification_store,
        changesets=SQLiteCandidateChangesetStore(root / "changesets.sqlite3"),
        recipe_catalog=recipes,
        git_delivery=LocalGitDeliveryService(
            authority, LocalGitAdapter(),
            SQLiteLocalGitDeliveryStore(root / "git-delivery.sqlite3"),
        ),
        runtime_diagnostic_service=RuntimeDiagnosticService(
            authority, RuntimeDiagnosticRecipePolicy(recipes),
            _DiagnosticRunner(), diagnostic_store,
        ),
        runtime_diagnostic_store=diagnostic_store,
    )
    generation = CandidateGenerationService(
        _Runtime(), "model:1",
        SQLiteCandidateGenerationStore(root / "generation.sqlite3"),
    )
    api = ProductNaturalEngineeringApi(
        "owner-1", SQLiteNaturalEngineeringProposalStore(
            root / "proposals.sqlite3",
        ),
        _Authentication(), authority, loop,
        BoundedFilesystemRepositoryObserver(),
        executor=NaturalEngineeringExecutionCoordinator(
            loop, BoundedCandidateContextReader(), generation,
        ),
        identifier=lambda: "runtime-diagnostic",
    )
    return api, loop


def _workspace(root):
    workspace = root / "project"
    workspace.mkdir()
    (workspace / "app.py").write_text("VALUE = 1\n")
    subprocess.run(("git", "init", "-q", str(workspace)), check=True)
    subprocess.run(("git", "-C", str(workspace), "add", "app.py"), check=True)
    subprocess.run((
        "git", "-C", str(workspace), "-c", "user.name=Test", "-c",
        "user.email=test@example.invalid", "commit", "-q", "-m", "initial",
    ), check=True)
    return workspace


class _Recipes:
    verification = SimpleNamespace(
        recipe_id="engineering.python.test", recipe_version="1.0.0",
        ecosystem=EngineeringEcosystem.PYTHON,
        executable_path="/usr/bin/python3", purpose=ToolRecipePurpose.TEST,
    )

    def __init__(self):
        private = Ed25519PrivateKey.from_private_bytes(b"\x09" * 32)
        self._catalog = SignedToolRecipeCatalog(
            Ed25519RecipeSignatureVerifier({
                "release-key": private.public_key(),
            }),
        )
        for specification in diagnostic_recipe_specifications():
            self._catalog.admit(sign_recipe_specification(
                specification, "release-key", private,
            ))

    def get(self, recipe_id, recipe_version):
        if (recipe_id, recipe_version) == (
            self.verification.recipe_id, self.verification.recipe_version,
        ):
            return self.verification
        return self._catalog.get(recipe_id, recipe_version)

    def matching(self, toolchain, purposes):
        return (self.verification,) if toolchain == "python3" else ()

    def matching_purposes(self, purposes):
        return self._catalog.matching_purposes(purposes)


class _Authority:
    def __init__(self):
        self.grant = None
        self.index = 0

    def activate(self, grant, approval):
        self.grant = grant

    def usable(self, grant_id):
        return self.grant if self.grant and self.grant.grant_id == grant_id else None

    def authorize(self, request):
        self.index += 1
        allowed = self.usable(request.grant_id) is not None
        return EngineeringAuthorizationDecision(
            f"decision-{self.index}", request.request_id, request.grant_id,
            request.authority, datetime.now(timezone.utc), allowed,
            "authorized" if allowed else "grant_unavailable",
        )


class _Authentication:
    def issue(self, owner_id, purpose, digest, transport_session_id=None):
        return SimpleNamespace(context_id=f"context:{transport_session_id}")

    def belongs_to_session(self, context_id, session_id):
        return context_id == f"context:{session_id}"


class _Runtime:
    def chat(self, request):
        return InferenceResponse(json.dumps({
            "contract_version": "fam.core.engineering/v1alpha1",
            "summary": "Replace app value",
            "operations": [{
                "kind": "replace_file", "path": "app.py",
                "content": "VALUE = 2\n", "source_path": None,
                "media_type": "text/x-python",
            }],
        }), InferenceMetrics("model:1", 0.1, 0.0, 20, 20))


class _VerificationRunner:
    def run(self, task_id, candidate, recipe_id, recipe_version, profile):
        now = datetime.now(timezone.utc)
        return EngineeringToolReceipt(
            f"tool-{candidate.candidate_id}", task_id, candidate.candidate_id,
            recipe_id, "a" * 64, profile.profile_id, "b" * 64, now, now, 0,
            "c" * 64, "d" * 64, (), (), ("sandbox",),
            ToolQualificationStatus.PASSED,
        )


class _Verifier:
    def verify(self, receipt, recipe_version):
        return SimpleNamespace(
            passed=True, verifier_ids=("verifier-1",), reason="passed",
        )


class _DiagnosticRunner:
    def run(self, request, candidate, profile, *, authorization_decision_ids):
        now = datetime.now(timezone.utc)
        empty = hashlib.sha256(b"").hexdigest()
        artifacts = ()
        baseline = request.baseline_artifact_sha256
        observed = regression = None
        if request.kind.value == "performance_regression":
            artifact = RuntimeDiagnosticArtifact(
                f"artifact-{request.request_id}", request.artifact_kinds[0],
                "text/plain", "f" * 64, 10, True,
            )
            artifacts = (artifact,)
            observed = (
                1_000_000
                if request.performance_mode is RuntimePerformanceMode.BASELINE_CAPTURE
                else 900_000
            )
            if request.performance_mode is RuntimePerformanceMode.BASELINE_CAPTURE:
                baseline = artifact.sha256
                regression = 0
            else:
                regression = -100_000
        return RuntimeDiagnosticReceipt(
            f"receipt-{request.request_id}", request.request_id,
            request.task_id, request.candidate_id, request.signed_recipe_id,
            request.signed_recipe_version, request.recipe_payload_sha256,
            profile.profile_id, now, now, RuntimeDiagnosticStatus.PASSED, 0,
            empty, empty, artifacts, (), ("sandbox",),
            authorization_decision_ids, baseline, observed, regression,
            performance_mode=request.performance_mode,
        )


if __name__ == "__main__":
    unittest.main()
