import hashlib
import json
import subprocess
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from fam_os.adapters.sqlite import SQLitePublicationConsumptionStore
from fam_os.core.engineering import (
    GitPublicationApproval,
    GitPublicationKind,
    GitPublicationReceipt,
    GitPublicationService,
)
from tests.contract.schema_engineering_fixtures import NOW, engineering_grant_schema_values


class _LocalTestProvider:
    def __init__(self, remote):
        self.remote = remote

    def publish(self, approval):
        old = _remote_oid(self.remote, approval.target_ref)
        if old != approval.expected_old_object_id:
            raise RuntimeError("test remote ref changed after approval")
        subprocess.run(
            ("git", "-C", approval.repository_root, "push", "--porcelain", approval.remote_name, f"{approval.source_ref}:{approval.target_ref}"),
            check=True, capture_output=True, text=True, timeout=30,
            env={"PATH": "/usr/bin:/bin", "HOME": "/nonexistent", "GIT_TERMINAL_PROMPT": "0"},
        )
        observed = _remote_oid(self.remote, approval.target_ref)
        draft = self.remote.parent / "draft-pr.json"
        draft.write_text(json.dumps({
            "draft": True, "title": approval.title, "body": approval.body,
            "target_ref": approval.target_ref, "new_object_id": observed,
        }, sort_keys=True))
        return GitPublicationReceipt(
            "test-publication-receipt", approval.approval_id,
            "local-test-provider", approval.remote_name, approval.target_ref,
            old, observed, draft.as_uri(), True, NOW,
            hashlib.sha256(draft.read_bytes()).hexdigest(),
        )


def _remote_oid(remote, ref):
    result = subprocess.run(
        ("git", "--git-dir", str(remote), "rev-parse", "--verify", ref),
        capture_output=True, text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else None


class GitPublicationExitTests(unittest.TestCase):
    def test_authorized_test_remote_push_and_draft_pr_are_exact_and_replay_safe(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            repository, remote = root / "repository", root / "remote.git"
            subprocess.run(("git", "init", "-q", "-b", "main", str(repository)), check=True)
            subprocess.run(("git", "init", "-q", "--bare", str(remote)), check=True)
            subprocess.run(("git", "-C", str(repository), "remote", "add", "origin", str(remote)), check=True)
            (repository / "feature.txt").write_text("verified feature\n")
            subprocess.run(("git", "-C", str(repository), "add", "feature.txt"), check=True)
            subprocess.run(("git", "-C", str(repository), "-c", "user.name=FAM OS", "-c", "user.email=fam@localhost", "commit", "-qm", "verified feature"), check=True)
            subprocess.run(("git", "-C", str(repository), "switch", "-qc", "feature/engineering"), check=True)
            oid = subprocess.run(("git", "-C", str(repository), "rev-parse", "HEAD"), check=True, capture_output=True, text=True).stdout.strip()
            diff = subprocess.run(("git", "-C", str(repository), "show", "--binary", "--format=", "HEAD"), check=True, capture_output=True).stdout
            approval = GitPublicationApproval(
                "publication-exit-1", "task-1", "grant-engineering-1",
                GitPublicationKind.DRAFT_CHANGE_REQUEST, str(repository),
                "origin", hashlib.sha256(str(remote).encode()).hexdigest(),
                "refs/heads/feature/engineering", "refs/heads/feature/engineering",
                None, oid, (oid,), hashlib.sha256(diff).hexdigest(),
                ("verification-polyglot", "verification-design"),
                "Verified engineering feature", "All deterministic gates passed.",
                "secret.git.test-origin", ("Publish one test branch and draft PR",),
                NOW, NOW + timedelta(minutes=5),
            )
            consumptions = SQLitePublicationConsumptionStore(root / "publication.sqlite3")
            service = GitPublicationService(_LocalTestProvider(remote), consumptions)
            receipt = service.publish(
                approval, engineering_grant_schema_values()[0],
                instant=NOW + timedelta(minutes=1),
            )
            self.assertEqual(oid, _remote_oid(remote, approval.target_ref))
            self.assertTrue(receipt.draft)
            self.assertTrue((root / "draft-pr.json").is_file())
            consumptions.close()
            restarted = SQLitePublicationConsumptionStore(root / "publication.sqlite3")
            with self.assertRaisesRegex(PermissionError, "consumed"):
                GitPublicationService(_LocalTestProvider(remote), restarted).publish(
                    approval, engineering_grant_schema_values()[0],
                    instant=NOW + timedelta(minutes=1),
                )
            restarted.close()


if __name__ == "__main__":
    unittest.main()
