import hashlib
import tempfile
import unittest
from pathlib import Path

from fam_os.adapters.filesystem.candidate_workspace import CandidateWorkspaceAdapter
from fam_os.core.engineering import (
    CandidateApplyStatus,
    CandidateArtifact,
    CandidateArtifactMetadata,
    CandidateContentKind,
    CandidateOperation,
    CandidateOperationKind,
    EngineeringSelfUpdatePolicy,
)
from tests.contract.schema_engineering_fixtures import NOW


class SelfHostedSourceModificationTests(unittest.TestCase):
    def test_declared_fam_source_checkout_can_modify_verify_apply_and_restore(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            checkout, transactions = root / "checkout", root / "transactions"
            source = checkout / "source/src/fam_os/example.py"
            source.parent.mkdir(parents=True)
            original = b"VALUE = 1\n"
            changed = b"VALUE: int = 2\n"
            source.write_bytes(original)
            policy = EngineeringSelfUpdatePolicy(
                ("source",), ("runtime",), ("trust",),
                ("releases/active",), ("policy/live",),
            )
            policy.authorize_source_path("source/src/fam_os/example.py")
            adapter = CandidateWorkspaceAdapter(checkout, transactions)
            candidate = adapter.create("task-self-host", now=NOW)
            artifact = CandidateArtifact(
                "self-source", CandidateContentKind.TEXT, "text/x-python",
                hashlib.sha256(changed).hexdigest(), len(changed),
                "approved self-hosted source candidate",
                "source/src/fam_os/example.py",
                (CandidateArtifactMetadata("self_update_policy", "source-only"),),
            )
            adapter.stage_artifact(candidate, artifact, changed)
            operation = CandidateOperation(
                "self-patch", CandidateOperationKind.PATCH_FILE,
                "source/src/fam_os/example.py", hashlib.sha256(original).hexdigest(),
                artifact.artifact_id,
            )
            adapter.execute(candidate, operation, {artifact.artifact_id: artifact})
            compile(
                (Path(candidate.candidate_workspace) / operation.path).read_text(),
                operation.path, "exec",
            )
            preview = adapter.preview(
                candidate, "self-transaction", (operation,),
                {artifact.artifact_id: artifact}, "self-hosted syntax passed",
                verification_evidence_ids=("python-compile",), now=NOW,
            )
            applied = adapter.reconcile(candidate, preview, (operation,), approved=True, now=NOW)
            self.assertEqual(CandidateApplyStatus.APPLIED, applied.status)
            self.assertEqual(changed, source.read_bytes())
            restored = adapter.recover(candidate, now=NOW)
            self.assertEqual(CandidateApplyStatus.ROLLED_BACK, restored.status)
            self.assertEqual(original, source.read_bytes())


if __name__ == "__main__":
    unittest.main()
