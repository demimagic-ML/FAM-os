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
    SQLiteEngineeringLoopStore, SQLiteEngineeringPreparationStore,
    SQLiteEngineeringReviewStore, SQLiteLocalGitDeliveryStore,
    SQLiteNaturalEngineeringProposalStore,
)
from fam_os.core.engineering import (
    CandidateGenerationService, CandidateVerificationService,
    EngineeringReviewExecutionService, EngineeringReviewService,
    LocalGitDeliveryService,
)
from fam_os.core.ports.inference import InferenceResponse
from fam_os.product.engineering_loop_api import ProductEngineeringLoopApi
from fam_os.product.natural_engineering_api import ProductNaturalEngineeringApi
from fam_os.product.natural_engineering_execution import (
    NaturalEngineeringExecutionCoordinator,
)
from fam_os.product.natural_engineering_review import (
    NaturalEngineeringReviewCoordinator,
)
from fam_os.adapters.review import DeterministicEngineeringReviewer
from fam_os.telemetry.contracts import InferenceMetrics
from tests.integration.test_natural_engineering_checkpoint import (
    _Authentication, _Authority, _Recipes, _Runner, _Verifier,
    _reviewer_recipes,
)


class NaturalEngineeringReviewIntegrationTests(unittest.TestCase):
    def test_signed_security_finding_blocks_then_exact_owner_waiver_reduces_assurance(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "project"
            workspace.mkdir()
            (workspace / "app.py").write_text("VALUE = 1\n")
            subprocess.run(("git", "init", "-q", str(workspace)), check=True)
            subprocess.run(("git", "-C", str(workspace), "add", "app.py"), check=True)
            subprocess.run((
                "git", "-C", str(workspace), "-c", "user.name=Test", "-c",
                "user.email=test@example.invalid", "commit", "-q", "-m", "initial",
            ), check=True)
            authority = _Authority()
            recipes = _Recipes()
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
                    authority, recipes, _Runner(), _Verifier(), verification_store,
                ),
                verification_store,
                SQLiteCandidateChangesetStore(root / "changesets.sqlite3"),
                recipes,
                LocalGitDeliveryService(
                    authority, LocalGitAdapter(),
                    SQLiteLocalGitDeliveryStore(root / "git.sqlite3"),
                ),
                None, None,
                EngineeringReviewService(SQLiteEngineeringReviewStore(
                    root / "reviews.sqlite3",
                )),
            )
            api = ProductNaturalEngineeringApi(
                "owner-1", SQLiteNaturalEngineeringProposalStore(
                    root / "proposals.sqlite3",
                ),
                _Authentication(), authority, loop,
                BoundedFilesystemRepositoryObserver(),
                executor=NaturalEngineeringExecutionCoordinator(
                    loop, BoundedCandidateContextReader(),
                    CandidateGenerationService(
                        _RiskRuntime(), "model:1",
                        SQLiteCandidateGenerationStore(root / "generation.sqlite3"),
                    ),
                    reviewer=NaturalEngineeringReviewCoordinator(
                        loop, EngineeringReviewExecutionService(
                            _reviewer_recipes(),
                            DeterministicEngineeringReviewer(),
                        ),
                    ),
                ),
                identifier=lambda: "review-integration",
            )
            proposal = api.propose(
                "owner-1", "Fix the Python security runner and run tests.",
                str(workspace),
            )
            blocked = api.activate(
                "owner-1", proposal["proposal_id"], "console-session-1",
                confirmed=True,
            )["engineering_task"]
            self.assertEqual("independent_review_blocked", blocked["outcome"])
            self.assertEqual("VALUE = 1\n", (workspace / "app.py").read_text())
            waiver = blocked["review_waiver_checkpoint"]
            with self.assertRaisesRegex(PermissionError, "consequences changed"):
                api.waive_review(
                    "owner-1", proposal["proposal_id"], waiver["checkpoint_id"],
                    waiver["finding_id"], "0" * 64, "console-session-1",
                    confirmed=True,
                )
            waived = api.waive_review(
                "owner-1", proposal["proposal_id"], waiver["checkpoint_id"],
                waiver["finding_id"], waiver["consequences_sha256"],
                "console-session-1", confirmed=True,
            )["engineering_task"]
            self.assertEqual("changeset_approval_required", waived["outcome"])
            self.assertEqual(
                "review_waived",
                waived["review_waiver"]["payload"]["truthful_assurance"],
            )
            changeset_id = waived["changeset"]["payload"]["changeset_id"]
            completed = api.approve_changeset(
                "owner-1", proposal["proposal_id"], changeset_id,
                "console-session-1", confirmed=True,
            )["engineering_task"]
            self.assertEqual("local_commit_completed", completed["outcome"])
            self.assertIn("os.system", (workspace / "app.py").read_text())
            api.close()
            loop.close()


class _RiskRuntime:
    def chat(self, request):
        return InferenceResponse(
            json.dumps({
                "contract_version": "fam.core.engineering/v1alpha1",
                "summary": "Change security runner",
                "operations": [{
                    "kind": "replace_file", "path": "app.py",
                    "content": "import os\nos.system('echo test')\n",
                    "source_path": None, "media_type": "text/x-python",
                }],
            }),
            InferenceMetrics("model:1", 0.1, 0.0, 20, 20),
        )


if __name__ == "__main__":
    unittest.main()
