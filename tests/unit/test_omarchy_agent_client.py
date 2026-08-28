import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fam_os.product.omarchy_agent_client import submit_from_omarchy


class _Response:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, *_args):
        return b'{"accepted":true}'


class OmarchyAgentClientTests(unittest.TestCase):
    def test_submission_has_a_unique_idempotency_key(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / "workspace"
            workspace.mkdir()
            runtime = root / "run"
            runtime.mkdir()
            token = runtime / "widget.token"
            token.write_text("secret-token", encoding="ascii")
            (runtime / "widget.json").write_text(json.dumps({
                "contractVersion": "fam.widget-runtime/v1",
                "endpoint": "http://127.0.0.1:8765",
                "tokenPath": str(token),
            }), encoding="utf-8")
            captured = []

            def open_request(request, timeout):
                captured.append((request, timeout))
                return _Response()

            with patch(
                "fam_os.product.omarchy_agent_client.urlopen", open_request,
            ):
                submit_from_omarchy(
                    "test it", workspace, goal_mode=True,
                    authority_profile="workspace", runtime_root=runtime,
                )
                submit_from_omarchy(
                    "test it", workspace, goal_mode=True,
                    authority_profile="workspace", runtime_root=runtime,
                )

            bodies = [json.loads(request.data) for request, _timeout in captured]
            self.assertRegex(bodies[0]["commandId"], r"^launcher-[0-9a-f]{32}$")
            self.assertNotEqual(bodies[0]["commandId"], bodies[1]["commandId"])
            self.assertEqual(bodies[0]["workspace_root"], str(workspace))
            self.assertEqual(captured[0][0].headers["X-fam-widget-token"], "secret-token")


if __name__ == "__main__":
    unittest.main()
