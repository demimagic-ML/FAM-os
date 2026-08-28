import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from fam_os.adapters.omarchy.context import collect_omarchy_context


class OmarchyContextTests(unittest.TestCase):
    def test_context_is_shaped_by_the_request(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            (workspace / "package.json").write_text(json.dumps({
                "scripts": {"dev": "vite", "test": "vitest run"},
            }))

            def run(command, **_kwargs):
                values = {
                    ("hyprctl", "-j", "activewindow"): json.dumps({
                        "class": "chromium", "title": "Calculator", "pid": 42,
                    }),
                    ("hyprctl", "-j", "activeworkspace"): json.dumps({
                        "id": 3, "name": "3", "monitor": "DP-1",
                    }),
                    ("ss", "-H", "-ltnp"): "LISTEN 0 10 127.0.0.1:5173 0.0.0.0:*",
                }
                return subprocess.CompletedProcess(command, 0, values.get(tuple(command), ""), "")

            context = collect_omarchy_context(
                workspace, "Run and test this browser app", "omarchy-scratchpad",
                run=run,
            )

            self.assertEqual("chromium", context["activeWindow"]["class"])
            self.assertEqual([5173], context["listeningTcpPorts"])
            self.assertEqual(["http://127.0.0.1:5173"], context["candidateBrowserEndpoints"])
            self.assertEqual("vite", context["projectCommands"]["dev"])

    def test_plain_repository_question_does_not_collect_desktop_or_ports(self):
        with tempfile.TemporaryDirectory() as directory:
            calls = []

            def run(command, **_kwargs):
                calls.append(command)
                return subprocess.CompletedProcess(command, 0, "", "")

            context = collect_omarchy_context(
                Path(directory), "Explain this repository", "omarchy-agent", run=run,
            )
            self.assertEqual([], calls)
            self.assertNotIn("activeWindow", context)
            self.assertNotIn("listeningTcpPorts", context)


if __name__ == "__main__":
    unittest.main()
