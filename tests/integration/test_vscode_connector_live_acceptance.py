import os
import shutil
import tempfile
import unittest
from pathlib import Path

from fam_os.application_acceptance import IsolatedVsCodeHost
from fam_os.applications import ObservationRequest, ObservationStatus


ROOT = Path(__file__).parents[2]


@unittest.skipUnless(
    os.environ.get("FAM_OS_RUN_VSCODE_LIVE") == "1",
    "live isolated VS Code acceptance is opt-in",
)
class LiveVsCodeConnectorAcceptanceTests(unittest.TestCase):
    def test_real_extension_observes_active_workspace_document(self):
        code = Path(shutil.which("code") or "")
        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw)
            target = workspace / "active.py"
            target.write_text("value = 1\n", encoding="utf-8")
            host = IsolatedVsCodeHost(code, ROOT / "connectors/vscode")
            with host.start(workspace, target):
                result = host.observe(ObservationRequest(
                    "live-observation", host.instance_id,
                    "vscode.editor.active", "live-grant",
                    resource_uri=target.as_uri(),
                ))
                self.assertIs(ObservationStatus.OBSERVED, result.status)
                self.assertEqual(target.as_uri(), result.payload["document_uri"])


if __name__ == "__main__":
    unittest.main()
