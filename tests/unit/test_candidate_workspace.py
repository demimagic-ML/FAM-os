"""Transactional candidate workspace, reconciliation, and recovery tests."""

from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import tempfile
import unittest

from fam_os.adapters.filesystem.candidate_workspace import CandidateWorkspaceAdapter
from fam_os.adapters.filesystem.candidate_verification import CandidateVerificationAdapter
from fam_os.core.engineering import (
    CandidateApplyStatus, CandidateArtifact, CandidateContentKind,
    CandidateArtifactMetadata, CandidateOperation, CandidateOperationKind,
    EngineeringSelfUpdatePolicy,
)


NOW = datetime(2026, 7, 18, 18, 0, tzinfo=timezone.utc)


def digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def artifact(identifier: str, content: bytes, *, binary=False) -> CandidateArtifact:
    return CandidateArtifact(
        identifier,
        CandidateContentKind.BINARY if binary else CandidateContentKind.TEXT,
        "image/png" if binary else "text/plain",
        digest(content), len(content), "generated for accepted engineering task",
        "asset.png" if binary else "source.txt",
        (CandidateArtifactMetadata("generator", "unit-test"),),
    )


class CandidateWorkspaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name).resolve()
        self.owner = root / "owner"
        self.transactions = root / "transactions"
        self.owner.mkdir()
        (self.owner / "src").mkdir()
        (self.owner / "src" / "main.py").write_text("print('old')\n", encoding="utf-8")
        (self.owner / "obsolete.txt").write_text("obsolete\n", encoding="utf-8")
        (self.owner / "tool.sh").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        os.chmod(self.owner / "tool.sh", 0o600)
        self.adapter = CandidateWorkspaceAdapter(self.owner, self.transactions)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _candidate_change(self):
        candidate = self.adapter.create("task-transaction", now=NOW)
        changed = b"print('new')\n"
        created = b"from src.main import *\n"
        binary = b"\x89PNG\r\n\x1a\nasset"
        artifacts = {
            item.artifact_id: item for item in (
                artifact("changed", changed), artifact("created", created),
                artifact("binary", binary, binary=True),
            )
        }
        for item, content in zip(artifacts.values(), (changed, created, binary), strict=True):
            self.adapter.stage_artifact(candidate, item, content)
        operations = (
            CandidateOperation("mkdir", CandidateOperationKind.CREATE_DIRECTORY, "tests"),
            CandidateOperation("patch", CandidateOperationKind.PATCH_FILE, "src/main.py", digest(b"print('old')\n"), "changed"),
            CandidateOperation("create", CandidateOperationKind.CREATE_FILE, "tests/test_main.py", None, "created"),
            CandidateOperation("asset", CandidateOperationKind.CREATE_FILE, "logo.png", None, "binary"),
            CandidateOperation("move", CandidateOperationKind.MOVE, "archive.txt", digest(b"obsolete\n"), source_path="obsolete.txt"),
            CandidateOperation("chmod", CandidateOperationKind.SET_EXECUTABLE, "tool.sh", digest(b"#!/bin/sh\nexit 0\n"), executable=True),
        )
        for operation in operations:
            self.adapter.execute(candidate, operation, artifacts)
        preview = self.adapter.preview(
            candidate, "transaction-1", operations, artifacts,
            "candidate tests passed in isolated workspace",
            verification_evidence_ids=("verification-1",), now=NOW,
        )
        return candidate, operations, preview

    def test_multi_file_text_binary_move_and_mode_change_apply_then_restore(self) -> None:
        candidate, operations, preview = self._candidate_change()
        self.assertTrue(all(str(self.owner) not in item.preview for item in preview.items))
        self.assertIn("binary asset", next(item.preview for item in preview.items if item.path == "logo.png"))
        self.assertEqual("print('old')\n", (self.owner / "src/main.py").read_text())

        verification = CandidateVerificationAdapter((Path("/usr/bin/python3"),)).run(
            candidate, ("/usr/bin/python3", "-m", "py_compile", "src/main.py"),
            environment={"PYTHONPATH": str(Path(candidate.candidate_workspace))},
        )
        self.assertTrue(verification.passed)
        self.assertTrue(verification.working_directory.startswith(candidate.candidate_workspace))
        self.assertEqual("print('old')\n", (self.owner / "src/main.py").read_text())

        receipt = self.adapter.reconcile(candidate, preview, operations, approved=True, now=NOW)
        self.assertEqual(CandidateApplyStatus.APPLIED, receipt.status)
        self.assertEqual("print('new')\n", (self.owner / "src/main.py").read_text())
        self.assertTrue(os.access(self.owner / "tool.sh", os.X_OK))
        self.assertFalse((self.owner / "obsolete.txt").exists())
        self.assertTrue((self.owner / "archive.txt").exists())

        restored = self.adapter.recover(candidate, now=NOW)
        self.assertEqual(CandidateApplyStatus.ROLLED_BACK, restored.status)
        self.assertEqual("print('old')\n", (self.owner / "src/main.py").read_text())
        self.assertFalse((self.owner / "tests").exists())
        self.assertFalse((self.owner / "logo.png").exists())
        self.assertTrue((self.owner / "obsolete.txt").exists())
        self.assertFalse(os.access(self.owner / "tool.sh", os.X_OK))

    def test_stale_baseline_rejects_entire_transaction_before_apply(self) -> None:
        candidate, operations, preview = self._candidate_change()
        (self.owner / "src/main.py").write_text("owner change\n", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "stale"):
            self.adapter.reconcile(candidate, preview, operations, approved=True)
        self.assertFalse((self.owner / "tests").exists())
        self.assertEqual("owner change\n", (self.owner / "src/main.py").read_text())

    def test_candidate_scan_ignores_verifier_generated_cache_directories(self) -> None:
        candidate = self.adapter.create("task-verifier-cache", now=NOW)
        candidate_root = Path(candidate.candidate_workspace)
        for directory in (
            "__pycache__", ".pytest_cache", ".mypy_cache", ".terraform",
            ".gradle", ".turbo", ".parcel-cache",
        ):
            cache = candidate_root / directory
            cache.mkdir()
            (cache / "generated.bin").write_bytes(b"verifier output")

        entries = self.adapter.current_entries(candidate)

        self.assertEqual(candidate.entries, entries)

    def test_candidate_creation_ignores_large_terraform_provider_cache(self) -> None:
        terraform = self.owner / "infrastructure" / ".terraform" / "providers"
        terraform.mkdir(parents=True)
        provider = terraform / "terraform-provider-example"
        with provider.open("wb") as stream:
            stream.truncate(self.adapter.maximum_bytes + 1)

        candidate = self.adapter.create("task-terraform-cache", now=NOW)

        self.assertFalse(any(
            entry.path.startswith("infrastructure/.terraform")
            for entry in candidate.entries
        ))

    def test_squashed_content_patch_discloses_and_applies_mode_change(self) -> None:
        candidate = self.adapter.create("task-mode", now=NOW)
        changed = b"print('new and executable')\n"
        changed_artifact = artifact("changed-mode", changed)
        self.adapter.stage_artifact(candidate, changed_artifact, changed)
        patch = CandidateOperation(
            "patch-mode", CandidateOperationKind.PATCH_FILE, "src/main.py",
            digest(b"print('old')\n"), changed_artifact.artifact_id,
        )
        self.adapter.execute(
            candidate, patch, {changed_artifact.artifact_id: changed_artifact},
        )
        self.adapter.execute(
            candidate,
            CandidateOperation(
                "candidate-mode", CandidateOperationKind.SET_EXECUTABLE,
                "src/main.py", digest(changed), executable=True,
            ),
            {},
        )

        preview = self.adapter.preview(
            candidate, "transaction-mode", (patch,),
            {changed_artifact.artifact_id: changed_artifact},
            "candidate tests passed", verification_evidence_ids=("verify-mode",),
            now=NOW,
        )

        self.assertIn("set_executable", preview.items[0].risk_codes)
        self.assertIn("executable mode: enabled", preview.items[0].preview)
        receipt = self.adapter.reconcile(
            candidate, preview, (patch,), approved=True, now=NOW,
        )
        self.assertEqual(CandidateApplyStatus.APPLIED, receipt.status)
        self.assertTrue(os.access(self.owner / "src/main.py", os.X_OK))

    def test_interrupted_apply_rolls_back_only_applied_changes(self) -> None:
        candidate, operations, preview = self._candidate_change()
        receipt = self.adapter.reconcile(
            candidate, preview, operations, approved=True, fault_after=3, now=NOW,
        )
        self.assertEqual(CandidateApplyStatus.ROLLED_BACK, receipt.status)
        self.assertTrue(receipt.rollback_complete)
        self.assertEqual("print('old')\n", (self.owner / "src/main.py").read_text())
        self.assertFalse((self.owner / "tests").exists())

    def test_recovery_preserves_owner_edit_made_during_partial_apply(self) -> None:
        candidate, operations, preview = self._candidate_change()

        def owner_intervenes(index, path):
            if index == 2:
                path.write_text("owner concurrent edit\n", encoding="utf-8")
                raise RuntimeError("interrupted after owner edit")

        receipt = self.adapter.reconcile(
            candidate, preview, operations, approved=True,
            after_apply=owner_intervenes, now=NOW,
        )
        self.assertEqual(CandidateApplyStatus.RECOVERY_REQUIRED, receipt.status)
        self.assertEqual(("src/main.py",), receipt.preserved_owner_paths)
        self.assertEqual("owner concurrent edit\n", (self.owner / "src/main.py").read_text())
        self.assertFalse((self.owner / "tests").exists())

    def test_symlink_tree_is_rejected(self) -> None:
        (self.owner / "escape").symlink_to(Path(self.temporary.name) / "outside")
        with self.assertRaisesRegex(PermissionError, "symbolic links"):
            CandidateWorkspaceAdapter(self.owner, self.transactions)

    def test_self_update_policy_allows_source_but_denies_runtime_and_trust_state(self) -> None:
        policy = EngineeringSelfUpdatePolicy(
            ("source",), ("runtime",), ("trust",), ("releases/active",), ("policy/live",),
        )
        policy.authorize_source_path("source/src/module.py")
        for path in ("runtime/bin/fam", "trust/root.pem", "releases/active/core", "policy/live/rules.json"):
            with self.assertRaises(PermissionError):
                policy.authorize_source_path(path)
        with self.assertRaises(PermissionError):
            policy.authorize_source_path("unrelated/module.py")


if __name__ == "__main__":
    unittest.main()
