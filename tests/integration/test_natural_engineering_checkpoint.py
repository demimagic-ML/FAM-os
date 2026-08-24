import json
import subprocess
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from fam_os.adapters.crypto.documentation_recipes import (
    sign_documentation_recipe_specification,
)
from fam_os.adapters.crypto.review_recipes import (
    sign_engineering_reviewer_recipe_specification,
)
from fam_os.adapters.review import DeterministicEngineeringReviewer
from fam_os.adapters.crypto.engineering_recipes import Ed25519RecipeSignatureVerifier
from fam_os.adapters.documentation import DeterministicDocumentationGenerator
from fam_os.adapters.filesystem import (
    BoundedCandidateContextReader, BoundedFilesystemRepositoryObserver,
)
from fam_os.adapters.git import LocalGitAdapter
from fam_os.adapters.sqlite import (
    SQLiteCandidateChangesetStore, SQLiteCandidateEditStore,
    SQLiteCandidateGenerationStore, SQLiteCandidateVerificationStore,
    SQLiteEngineeringLoopStore, SQLiteEngineeringPreparationStore,
    SQLiteNaturalEngineeringProposalStore,
    SQLiteLocalGitDeliveryStore,
    SQLiteEngineeringDocumentationStore,
    SQLiteEngineeringReviewStore,
)
from fam_os.core.engineering import (
    CandidateGenerationService, CandidateVerificationService,
    EngineeringAuthorizationDecision, EngineeringEcosystem,
    EngineeringToolReceipt, ToolQualificationStatus, ToolRecipePurpose,
    LocalGitDeliveryService,
    DocumentationGenerationService, SignedDocumentationRecipeCatalog,
    EngineeringReviewExecutionService, EngineeringReviewService,
    SignedEngineeringReviewerCatalog,
)
from fam_os.core.engineering.production_documentation_recipes import (
    initial_documentation_recipe_specifications,
)
from fam_os.core.engineering.production_review_recipes import (
    initial_engineering_reviewer_recipe_specification,
)
from fam_os.core.ports.inference import InferenceResponse
from fam_os.product.engineering_loop_api import ProductEngineeringLoopApi
from fam_os.product.natural_engineering_api import ProductNaturalEngineeringApi
from fam_os.product.natural_engineering_execution import (
    NaturalEngineeringExecutionCoordinator,
)
from fam_os.product.natural_engineering_documentation import (
    NaturalEngineeringDocumentationCoordinator,
)
from fam_os.product.natural_engineering_review import (
    NaturalEngineeringReviewCoordinator,
)
from fam_os.telemetry.contracts import InferenceMetrics


class NaturalEngineeringCheckpointIntegrationTests(unittest.TestCase):
    def test_natural_request_reaches_verified_checkpoint_without_owner_effect(self):
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
            documentation_recipes = _documentation_recipes()
            reviewer_recipes = _reviewer_recipes()
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
                    SQLiteLocalGitDeliveryStore(root / "git-delivery.sqlite3"),
                ),
                None, None,
                EngineeringReviewService(SQLiteEngineeringReviewStore(
                    root / "reviews.sqlite3",
                )),
                SQLiteEngineeringDocumentationStore(
                    root / "documentation.sqlite3",
                ),
                documentation_recipes,
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
                    NaturalEngineeringDocumentationCoordinator(
                        loop, DocumentationGenerationService(
                            documentation_recipes,
                            DeterministicDocumentationGenerator(),
                        ),
                    ),
                    NaturalEngineeringReviewCoordinator(
                        loop, EngineeringReviewExecutionService(
                            reviewer_recipes,
                            DeterministicEngineeringReviewer(),
                        ),
                    ),
                ),
                identifier=lambda: "checkpoint",
            )
            proposal = api.propose(
                "owner-1", "Replace the Python API value with 2 and run tests.",
                str(workspace),
            )
            result = api.activate(
                "owner-1", proposal["proposal_id"], "console-session-1",
                confirmed=True,
            )

            task = result["engineering_task"]
            self.assertEqual("changeset_approval_required", task["stage"])
            self.assertEqual("changeset_approval_required", task["outcome"])
            self.assertEqual("VALUE = 1\n", (workspace / "app.py").read_text())
            candidate = loop.preparation("owner-1", task["task_id"]).candidate
            self.assertEqual(
                "VALUE = 2\n", (Path(candidate.candidate_workspace) / "app.py").read_text(),
            )
            self.assertTrue((
                Path(candidate.candidate_workspace)
                / "docs/generated/fam-api-reference.md"
            ).is_file())
            self.assertEqual(2, len(tuple(
                item for item in loop.documentation_for_task(
                    "owner-1", task["task_id"],
                ) if type(item).__name__ in {
                    "DocumentationGenerationRequest",
                    "GeneratedDocumentationReceipt",
                }
            )))
            self.assertEqual(1, len(loop.candidate_verifications(
                "owner-1", task["task_id"],
            )))
            self.assertEqual(1, len(loop.candidate_changesets(
                "owner-1", task["task_id"],
            )))
            self.assertEqual(1, len(loop.reviews_for_task(
                "owner-1", task["task_id"],
            )))
            self.assertEqual("passed", task["review"]["payload"]["status"])
            completed = api.approve_changeset(
                "owner-1", proposal["proposal_id"],
                task["changeset"]["payload"]["changeset_id"],
                "console-session-1", confirmed=True,
            )
            self.assertEqual(
                "local_commit_completed",
                completed["engineering_task"]["outcome"],
            )
            self.assertEqual("committed", completed["engineering_task"]["stage"])
            self.assertEqual("VALUE = 2\n", (workspace / "app.py").read_text())
            self.assertEqual(
                "FAM: Replace the Python API value with 2 and run tests.",
                subprocess.run(
                    ("git", "-C", str(workspace), "show", "-s", "--format=%B", "HEAD"),
                    check=True, capture_output=True, text=True,
                ).stdout.strip(),
            )
            self.assertEqual(2, len(loop.candidate_verifications(
                "owner-1", task["task_id"],
            )))
            rollback = completed["engineering_task"]["rollback_checkpoint"]
            rolled_back = api.rollback(
                "owner-1", proposal["proposal_id"], rollback["rollback_id"],
                "console-session-1", confirmed=True,
            )
            self.assertEqual(
                "rollback_completed",
                rolled_back["engineering_task"]["outcome"],
            )
            self.assertEqual("rolled_back", rolled_back["engineering_task"]["stage"])
            self.assertEqual("VALUE = 1\n", (workspace / "app.py").read_text())
            self.assertEqual(
                "FAM rollback: Replace the Python API value with 2 and run tests.",
                subprocess.run(
                    ("git", "-C", str(workspace), "show", "-s", "--format=%B", "HEAD"),
                    check=True, capture_output=True, text=True,
                ).stdout.strip(),
            )
            self.assertEqual(
                3,
                int(subprocess.run(
                    ("git", "-C", str(workspace), "rev-list", "--count", "HEAD"),
                    check=True, capture_output=True, text=True,
                ).stdout),
            )
            progress = api.progress("owner-1", proposal["proposal_id"])
            self.assertEqual(
                "rollback_completed", progress["engineering_task"]["outcome"],
            )
            api.close()
            loop.close()


class _Authentication:
    def issue(self, owner_id, purpose, digest, transport_session_id=None):
        return SimpleNamespace(context_id=f"context:{transport_session_id}")

    def belongs_to_session(self, context_id, session_id):
        return context_id == f"context:{session_id}"


class _Authority:
    def __init__(self):
        self.grant = None
        self.index = 0

    def activate(self, grant, approval):
        self.grant = grant

    def usable(self, grant_id):
        return self.grant if self.grant is not None and self.grant.grant_id == grant_id else None

    def authorize(self, request):
        self.index += 1
        allowed = self.usable(request.grant_id) is not None
        return EngineeringAuthorizationDecision(
            f"decision-{self.index}", request.request_id, request.grant_id,
            request.authority, datetime.now(timezone.utc), allowed,
            "authorized" if allowed else "grant_unavailable",
        )


class _Recipes:
    recipe = SimpleNamespace(
        recipe_id="engineering.python.test", recipe_version="1.0.0",
        ecosystem=EngineeringEcosystem.PYTHON,
        executable_path="/usr/bin/python3", purpose=ToolRecipePurpose.TEST,
    )

    def get(self, recipe_id, recipe_version):
        if (recipe_id, recipe_version) != (
            self.recipe.recipe_id, self.recipe.recipe_version,
        ):
            raise LookupError("recipe unavailable")
        return self.recipe

    def matching(self, toolchain, purposes):
        return (self.recipe,) if toolchain == "python3" else ()


def _documentation_recipes():
    private = Ed25519PrivateKey.from_private_bytes(b"\x03" * 32)
    catalog = SignedDocumentationRecipeCatalog(
        Ed25519RecipeSignatureVerifier({"release-key": private.public_key()}),
    )
    for specification in initial_documentation_recipe_specifications():
        catalog.admit(sign_documentation_recipe_specification(
            specification, "release-key", private,
        ))
    return catalog


def _reviewer_recipes():
    private = Ed25519PrivateKey.from_private_bytes(b"\x04" * 32)
    catalog = SignedEngineeringReviewerCatalog(
        Ed25519RecipeSignatureVerifier({"release-key": private.public_key()}),
    )
    catalog.admit(sign_engineering_reviewer_recipe_specification(
        initial_engineering_reviewer_recipe_specification(),
        "release-key", private,
    ))
    return catalog


class _Runtime:
    def chat(self, request):
        return InferenceResponse(
            json.dumps({
                "contract_version": "fam.core.engineering/v1alpha1",
                "summary": "Replace app value",
                "operations": [{
                    "kind": "replace_file", "path": "app.py",
                    "content": "VALUE = 2\n", "source_path": None,
                    "media_type": "text/x-python",
                }],
            }),
            InferenceMetrics("model:1", 0.1, 0.0, 20, 20),
        )


class _Runner:
    def run(self, task_id, candidate, recipe_id, recipe_version, profile):
        now = datetime.now(timezone.utc)
        return EngineeringToolReceipt(
            "tool-natural-1", task_id, candidate.candidate_id, recipe_id,
            "a" * 64, profile.profile_id, "b" * 64, now, now, 0,
            "c" * 64, "d" * 64, (), (),
            ("bubblewrap-unshare-all", "cgroup-v2-systemd", "bounded-rlimits"),
            ToolQualificationStatus.PASSED,
        )


class _Verifier:
    def verify(self, receipt, recipe_version):
        return SimpleNamespace(
            passed=True, verifier_ids=("verifier-natural-1",), reason="passed",
        )


if __name__ == "__main__":
    unittest.main()
