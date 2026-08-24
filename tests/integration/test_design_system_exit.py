import hashlib
import tempfile
import unittest
from pathlib import Path

from fam_os.adapters.filesystem.candidate_workspace import CandidateWorkspaceAdapter
from fam_os.adapters.media.browser_capture import LocalResponsiveBrowserCapture
from fam_os.adapters.media.design_assets import DesignAssetSanitizer, contrast_ratio, visual_difference
from fam_os.core.engineering import (
    CandidateApplyStatus,
    CandidateArtifact,
    CandidateArtifactMetadata,
    CandidateContentKind,
    CandidateOperation,
    CandidateOperationKind,
)
from tests.contract.schema_engineering_fixtures import NOW


def _digest(value):
    return hashlib.sha256(value).hexdigest()


def _artifact(identity, path, content, mime):
    return CandidateArtifact(
        identity,
        CandidateContentKind.TEXT,
        mime,
        _digest(content),
        len(content),
        "approved design-system fixture",
        path,
        (CandidateArtifactMetadata("brief", "brief-design-exit"),),
    )


class DesignSystemExitTests(unittest.TestCase):
    def test_web_design_candidate_captures_responsive_states_and_restores(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            owner, transactions = root / "owner", root / "transactions"
            owner.mkdir()
            original = b"<!doctype html><html><body>old</body></html>\n"
            (owner / "index.html").write_bytes(original)
            adapter = CandidateWorkspaceAdapter(owner, transactions)
            candidate = adapter.create("task-design-exit", now=NOW)
            html = b'<!doctype html><html lang="en"><head><link rel="stylesheet" href="styles.css"></head><body><main><h1>FAM tasks</h1><button>Review change</button></main></body></html>\n'
            css = b':root { --text: #111111; --surface: #ffffff; } body { color: var(--text); background: var(--surface); } button:focus { outline: 3px solid #005fcc; } @media (max-width: 480px) { main { padding: 8px; } }\n'
            svg = DesignAssetSanitizer().sanitize_svg(
                b'<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32"><title>Task</title><path d="M2 2h28v28H2z"/></svg>'
            ).content
            values = (
                ("html", "index.html", html, "text/html", _digest(original), CandidateOperationKind.PATCH_FILE),
                ("css", "styles.css", css, "text/css", None, CandidateOperationKind.CREATE_FILE),
                ("icon", "assets/task.svg", svg, "image/svg+xml", None, CandidateOperationKind.CREATE_FILE),
            )
            artifacts = {}
            operations = []
            for identity, path, content, mime, before, kind in values:
                artifact = _artifact(identity, path, content, mime)
                artifacts[identity] = artifact
                adapter.stage_artifact(candidate, artifact, content)
                operation = CandidateOperation(identity, kind, path, before, identity)
                operations.append(operation)
                adapter.execute(candidate, operation, artifacts)
            candidate_root = Path(candidate.candidate_workspace)
            capture = LocalResponsiveBrowserCapture()
            narrow = capture.capture(candidate_root, "index.html", candidate_root / ".fam/narrow.png", width=360, height=640)
            wide = capture.capture(candidate_root, "index.html", candidate_root / ".fam/wide.png", width=1280, height=720)
            self.assertNotEqual(narrow.png_sha256, wide.png_sha256)
            self.assertEqual("external-network-resolution-denied", narrow.network_policy)
            self.assertGreater(contrast_ratio("#111111", "#ffffff"), 4.5)
            self.assertGreater(
                visual_difference(
                    (candidate_root / ".fam/narrow.png").read_bytes(),
                    (candidate_root / ".fam/wide.png").read_bytes(),
                ),
                0,
            )
            preview = adapter.preview(
                candidate, "design-transaction", tuple(operations), artifacts,
                "format, contrast, accessibility, responsive capture, and SVG checks passed",
                verification_evidence_ids=(narrow.png_sha256, wide.png_sha256), now=NOW,
            )
            applied = adapter.reconcile(candidate, preview, tuple(operations), approved=True, now=NOW)
            self.assertEqual(CandidateApplyStatus.APPLIED, applied.status)
            self.assertTrue((owner / "assets/task.svg").is_file())
            restored = adapter.recover(candidate, now=NOW)
            self.assertEqual(CandidateApplyStatus.ROLLED_BACK, restored.status)
            self.assertEqual(original, (owner / "index.html").read_bytes())
            self.assertFalse((owner / "styles.css").exists())


if __name__ == "__main__":
    unittest.main()
