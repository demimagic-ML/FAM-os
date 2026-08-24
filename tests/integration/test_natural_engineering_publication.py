"""Natural language through exact separately approved Git publication."""

import hashlib
import subprocess
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from fam_os.adapters.filesystem import (
    BoundedCandidateContextReader, BoundedFilesystemRepositoryObserver,
)
from fam_os.adapters.git import LocalGitAdapter
from fam_os.adapters.sqlite import (
    SQLiteCandidateChangesetStore, SQLiteCandidateEditStore,
    SQLiteCandidateGenerationStore, SQLiteCandidateVerificationStore,
    SQLiteEngineeringLoopStore, SQLiteEngineeringPreparationStore,
    SQLiteGitPublicationProposalStore, SQLiteLocalGitDeliveryStore,
    SQLiteNaturalEngineeringProposalStore,
    SQLitePublicationConsumptionStore,
)
from fam_os.core.engineering import (
    CandidateGenerationService, CandidateVerificationService,
    EngineeringAuthorizationDecision, GitPublicationProposal,
    GitPublicationReceipt, GitPublicationService, GitRemoteRefObservation,
    LocalGitDeliveryService,
)
from fam_os.product.engineering_loop_api import ProductEngineeringLoopApi
from fam_os.product.natural_engineering_api import ProductNaturalEngineeringApi
from fam_os.product.natural_engineering_execution import (
    NaturalEngineeringExecutionCoordinator,
)
from fam_os.schemas import dumps_document, loads_document
from tests.integration.test_natural_engineering_checkpoint import (
    _Authentication, _Recipes, _Runner, _Runtime, _Verifier,
)


class NaturalEngineeringPublicationIntegrationTests(unittest.TestCase):
    def test_natural_request_prepares_separate_grant_and_publishes_once(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace, remote = root / "project", root / "remote.git"
            workspace.mkdir()
            subprocess.run(
                ("git", "init", "-q", "-b", "main", str(workspace)),
                check=True,
            )
            subprocess.run(("git", "init", "-q", "--bare", str(remote)), check=True)
            subprocess.run(
                ("git", "-C", str(workspace), "remote", "add", "origin", str(remote)),
                check=True,
            )
            (workspace / "app.py").write_text("VALUE = 1\n")
            subprocess.run(("git", "-C", str(workspace), "add", "app.py"), check=True)
            subprocess.run((
                "git", "-C", str(workspace), "-c", "user.name=Test", "-c",
                "user.email=test@example.invalid", "commit", "-qm", "initial",
            ), check=True)
            authority, recipes = _MultiAuthority(), _Recipes()
            verifications = SQLiteCandidateVerificationStore(
                root / "verifications.sqlite3",
            )
            provider = _LocalPublicationProvider(remote)
            publication = GitPublicationService(
                provider,
                SQLitePublicationConsumptionStore(root / "consumption.sqlite3"),
                SQLiteGitPublicationProposalStore(
                    root / "publication-proposals.sqlite3",
                    _Codec(GitPublicationProposal), _Codec(GitPublicationReceipt),
                ),
            )
            loop = ProductEngineeringLoopApi(
                "owner-1", authority,
                SQLiteEngineeringLoopStore(root / "loop.sqlite3"),
                root / "candidates",
                SQLiteEngineeringPreparationStore(root / "preparation.sqlite3"),
                authority, SQLiteCandidateEditStore(root / "edits.sqlite3"),
                CandidateVerificationService(
                    authority, recipes, _Runner(), _Verifier(), verifications,
                ),
                verifications,
                SQLiteCandidateChangesetStore(root / "changesets.sqlite3"),
                recipes,
                LocalGitDeliveryService(
                    authority, LocalGitAdapter(),
                    SQLiteLocalGitDeliveryStore(root / "git-delivery.sqlite3"),
                ),
                publication,
            )
            api = ProductNaturalEngineeringApi(
                "owner-1",
                SQLiteNaturalEngineeringProposalStore(root / "proposals.sqlite3"),
                _Authentication(), authority, loop,
                BoundedFilesystemRepositoryObserver(),
                executor=NaturalEngineeringExecutionCoordinator(
                    loop, BoundedCandidateContextReader(),
                    CandidateGenerationService(
                        _Runtime(), "model:1",
                        SQLiteCandidateGenerationStore(root / "generation.sqlite3"),
                    ),
                ),
                publication_remote_name="origin",
                publication_credential_ref="secret.git.test-origin",
            )
            proposal = api.propose(
                "owner-1",
                "Replace the Python value with 2, run tests, push, and open a pull request.",
                str(workspace),
            )
            self.assertEqual(
                ["publish"], proposal["separately_confirmed_authorities"],
            )
            checkpoint = api.activate(
                "owner-1", proposal["proposal_id"], "console-session-1",
                confirmed=True,
            )["engineering_task"]
            published = api.approve_changeset(
                "owner-1", proposal["proposal_id"],
                checkpoint["changeset"]["payload"]["changeset_id"],
                "console-session-1", confirmed=True,
            )["engineering_task"]
            self.assertEqual("publication_approval_required", published["outcome"])
            publication_view = published["publication_proposal"]
            publication_payload = publication_view["document"]["payload"]
            self.assertEqual("prepared", publication_view["status"])
            self.assertEqual("origin", publication_payload["remote_name"])
            self.assertTrue(
                publication_payload["source_ref"].startswith("refs/heads/fam/"),
            )
            self.assertEqual(
                publication_payload["source_ref"],
                publication_payload["target_ref"],
            )
            delivery = published["git_delivery"]["payload"]
            self.assertEqual(
                "create_branch", delivery["branch_action"]["kind"],
            )
            self.assertIsNotNone(delivery["branch_receipt"])
            self.assertIsNone(publication_payload["expected_old_object_id"])
            self.assertEqual(
                ["publish", "secret_use"],
                publication_payload["grant"]["authorities"],
            )
            completed = api.approve_publication(
                "owner-1", proposal["proposal_id"],
                publication_payload["proposal_id"], "console-session-1",
                confirmed=True,
            )["engineering_task"]
            self.assertEqual("publication_completed", completed["outcome"])
            self.assertEqual("completed", completed["stage"])
            self.assertEqual(1, provider.publish_calls)
            self.assertEqual(
                completed["publication_receipt"]["payload"]["published_new_object_id"],
                _remote_oid(remote, publication_payload["target_ref"]),
            )
            replay = api.approve_publication(
                "owner-1", proposal["proposal_id"],
                publication_payload["proposal_id"], "console-session-1",
                confirmed=True,
            )["engineering_task"]
            self.assertEqual("publication_completed", replay["outcome"])
            self.assertEqual(1, provider.publish_calls)
            progress = api.progress("owner-1", proposal["proposal_id"])
            self.assertEqual(
                "publication_completed", progress["engineering_task"]["outcome"],
            )
            api.close()
            loop.close()


class _MultiAuthority:
    def __init__(self):
        self.grants = {}
        self.index = 0

    def activate(self, grant, approval):
        if grant.grant_id in self.grants:
            raise PermissionError("grant already activated")
        self.grants[grant.grant_id] = grant

    def usable(self, grant_id):
        return self.grants.get(grant_id)

    def authorize(self, request):
        self.index += 1
        allowed = request.grant_id in self.grants
        return EngineeringAuthorizationDecision(
            f"decision-{self.index}", request.request_id, request.grant_id,
            request.authority, datetime.now(timezone.utc), allowed,
            "authorized" if allowed else "grant_unavailable",
        )


class _LocalPublicationProvider:
    def __init__(self, remote):
        self.remote = remote
        self.publish_calls = 0

    def observe(self, request):
        return GitRemoteRefObservation(
            "remote-observation-1", request.request_id, "test-provider",
            request.remote_name, request.remote_url_sha256, request.target_ref,
            _remote_oid(self.remote, request.target_ref),
            datetime.now(timezone.utc), hashlib.sha256(b"observed").hexdigest(),
        )

    def publish(self, approval):
        self.publish_calls += 1
        old = _remote_oid(self.remote, approval.target_ref)
        if old != approval.expected_old_object_id:
            raise RuntimeError("remote ref changed after approval")
        subprocess.run((
            "git", "-C", approval.repository_root, "push", "--porcelain",
            approval.remote_name,
            f"{approval.source_ref}:{approval.target_ref}",
        ), check=True, capture_output=True, text=True, timeout=30, env={
            "PATH": "/usr/bin:/bin", "HOME": "/nonexistent",
            "GIT_TERMINAL_PROMPT": "0",
        })
        observed = _remote_oid(self.remote, approval.target_ref)
        return GitPublicationReceipt(
            "publication-receipt-1", approval.approval_id, "test-provider",
            approval.remote_name, approval.target_ref, old, observed,
            "https://git.example/draft/1", True, datetime.now(timezone.utc),
            hashlib.sha256(b"published").hexdigest(),
        )


class _Codec:
    def __init__(self, expected):
        self.expected = expected

    def encode(self, identity, value):
        return dumps_document(value)

    def decode(self, identity, token):
        value = loads_document(token)
        if not isinstance(value, self.expected):
            raise TypeError("unexpected test publication contract")
        return value


def _remote_oid(remote, ref):
    result = subprocess.run(
        ("git", "--git-dir", str(remote), "rev-parse", "--verify", ref),
        capture_output=True, text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else None


if __name__ == "__main__":
    unittest.main()
