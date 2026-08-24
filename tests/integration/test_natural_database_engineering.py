import json
import sqlite3
import subprocess
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from fam_os.adapters.database import (
    NaturalSQLitePlanBuilder, SQLiteDatabaseEngineeringAdapter,
    SQLiteDatabaseRecoveryAdapter,
)
from fam_os.adapters.filesystem import (
    BoundedCandidateContextReader, BoundedFilesystemRepositoryObserver,
)
from fam_os.adapters.git import LocalGitAdapter
from fam_os.adapters.sqlite import (
    SQLiteCandidateChangesetStore, SQLiteCandidateEditStore,
    SQLiteCandidateGenerationStore, SQLiteCandidateVerificationStore,
    SQLiteDatabaseEngineeringStore, SQLiteEngineeringLoopStore,
    SQLiteEngineeringPreparationStore, SQLiteLocalGitDeliveryStore,
    SQLiteNaturalEngineeringProposalStore,
)
from fam_os.core.engineering import (
    CandidateGenerationService, DatabaseEngineeringService,
    EngineeringAuthorizationDecision, LocalGitDeliveryService,
)
from fam_os.core.ports.inference import InferenceResponse
from fam_os.product.engineering_loop_api import ProductEngineeringLoopApi
from fam_os.product.natural_engineering_api import ProductNaturalEngineeringApi
from fam_os.product.natural_engineering_execution import (
    NaturalEngineeringExecutionCoordinator,
)
from fam_os.telemetry.contracts import InferenceMetrics


class NaturalDatabaseEngineeringIntegrationTests(unittest.TestCase):
    def test_natural_sqlite_migration_checkpoint_apply_reverify_and_rollback(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            workspace = _workspace(root)
            api, loop = _system(root)
            proposal = api.propose(
                "owner-1",
                "Create a SQLite schema migration for app.db adding a notes table.",
                str(workspace),
            )
            activated = api.activate(
                "owner-1", proposal["proposal_id"], "console-session-1",
                confirmed=True,
            )["engineering_task"]

            self.assertEqual("changeset_approval_required", activated["outcome"])
            database = activated["database_engineering"]
            self.assertEqual(
                "verified", database["verification"]["payload"]["status"],
            )
            receipt_id = database["verification"]["payload"]["receipt_id"]
            preview = activated["changeset"]["payload"]["preview"]
            self.assertIn(receipt_id, preview["verification_evidence_ids"])
            self.assertIn("app.db", {
                item["path"] for item in preview["items"]
            })
            self.assertEqual(["users"], _tables(workspace / "app.db"))

            completed = api.approve_changeset(
                "owner-1", proposal["proposal_id"],
                activated["changeset"]["payload"]["changeset_id"],
                "console-session-1", confirmed=True,
            )["engineering_task"]

            self.assertEqual("local_commit_completed", completed["outcome"])
            self.assertEqual(["notes", "users"], _tables(workspace / "app.db"))
            self.assertTrue(
                completed["postapply_database_receipts"][0]["payload"]["passed"]
            )
            checkpoint = completed["rollback_checkpoint"]
            rolled_back = api.rollback(
                "owner-1", proposal["proposal_id"], checkpoint["rollback_id"],
                "console-session-1", confirmed=True,
            )["engineering_task"]
            self.assertEqual("rollback_completed", rolled_back["outcome"])
            self.assertEqual(["users"], _tables(workspace / "app.db"))
            api.close()
            loop.close()


def _system(root):
    authority = _Authority()
    protector = _Protector()
    recovery = SQLiteDatabaseRecoveryAdapter(protector)
    database_store = SQLiteDatabaseEngineeringStore(
        root / "database.sqlite3",
    )
    loop = ProductEngineeringLoopApi(
        "owner-1", authority,
        SQLiteEngineeringLoopStore(root / "loop.sqlite3"),
        root / "candidates",
        SQLiteEngineeringPreparationStore(root / "preparation.sqlite3"),
        authorizer=authority,
        edits=SQLiteCandidateEditStore(root / "edits.sqlite3"),
        verifications=SQLiteCandidateVerificationStore(
            root / "verifications.sqlite3",
        ),
        changesets=SQLiteCandidateChangesetStore(root / "changesets.sqlite3"),
        git_delivery=LocalGitDeliveryService(
            authority, LocalGitAdapter(),
            SQLiteLocalGitDeliveryStore(root / "git.sqlite3"),
        ),
        database_builder=NaturalSQLitePlanBuilder("host-1"),
        database_service=DatabaseEngineeringService(
            authority, SQLiteDatabaseEngineeringAdapter(protector),
            recovery=recovery,
        ),
        database_store=database_store,
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
                _Runtime(), "model:1",
                SQLiteCandidateGenerationStore(root / "generation.sqlite3"),
            ),
        ),
        identifier=lambda: "natural-database",
    )
    return api, loop


def _workspace(root):
    workspace = root / "project"
    workspace.mkdir()
    connection = sqlite3.connect(workspace / "app.db")
    connection.execute(
        "CREATE TABLE users(id INTEGER PRIMARY KEY, name TEXT NOT NULL) STRICT",
    )
    connection.commit()
    connection.close()
    subprocess.run(("git", "init", "-q", str(workspace)), check=True)
    subprocess.run(("git", "-C", str(workspace), "add", "app.db"), check=True)
    subprocess.run((
        "git", "-C", str(workspace), "-c", "user.name=Test", "-c",
        "user.email=test@example.invalid", "commit", "-q", "-m", "initial",
    ), check=True)
    return workspace


def _tables(database):
    connection = sqlite3.connect(database)
    try:
        return [row[0] for row in connection.execute(
            "SELECT name FROM sqlite_schema WHERE type='table' ORDER BY name"
        )]
    finally:
        connection.close()


class _Protector:
    def encrypt(self, plaintext, context):
        return b"protected:" + context.encode("ascii") + b":" + plaintext[::-1]

    def decrypt(self, ciphertext, context):
        prefix = b"protected:" + context.encode("ascii") + b":"
        if not ciphertext.startswith(prefix):
            raise ValueError("database backup authentication failed")
        return ciphertext[len(prefix):][::-1]


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
        document = {
            "contract_version": "fam.core.engineering/v1alpha1",
            "summary": "Add a reversible notes schema migration",
            "operations": [
                {
                    "kind": "create_file", "path": "db/001.sql",
                    "content": (
                        "CREATE TABLE notes(id INTEGER PRIMARY KEY, "
                        "body TEXT NOT NULL) STRICT;"
                    ),
                    "source_path": None, "media_type": "text/x-sql",
                },
                {
                    "kind": "create_file", "path": "db/001_down.sql",
                    "content": "DROP TABLE notes;", "source_path": None,
                    "media_type": "text/x-sql",
                },
            ],
        }
        return InferenceResponse(
            json.dumps(document), InferenceMetrics("model:1", 0.1, 0.0, 20, 20),
        )


if __name__ == "__main__":
    unittest.main()
