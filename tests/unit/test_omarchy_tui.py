import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fam_os.product.omarchy_tui import run_omarchy_tui


class OmarchyTuiTests(unittest.TestCase):
    def test_goal_mode_submits_and_returns_to_an_interactive_prompt(self):
        with tempfile.TemporaryDirectory() as directory:
            values = iter(("/goal Build and test it", "/status", "/quit"))
            output = []
            status = {
                "engineeringProvider": "codex-subscription",
                "goal": {
                    "goalId": "goal-1",
                    "title": "Build it",
                    "status": "running",
                    "phase": "implementation",
                    "plan": {"current": 2, "total": 5},
                    "checks": {"passed": 1, "total": 3},
                    "tool": "write_file",
                },
            }
            with (
                patch(
                    "fam_os.product.omarchy_tui.submit_from_omarchy",
                    return_value={"goal_id": "goal-1", "title": "Build it"},
                ) as submit,
                patch(
                    "fam_os.product.omarchy_tui.widget_request",
                    return_value=status,
                ),
            ):
                result = run_omarchy_tui(
                    Path(directory),
                    authority_profile="workspace",
                    runtime_root=Path(directory) / "run",
                    read=lambda _prompt: next(values),
                    write=output.append,
                )

            self.assertEqual(0, result)
            self.assertTrue(submit.call_args.kwargs["goal_mode"])
            self.assertTrue(
                any("Provider: codex-subscription" in line for line in output)
            )
            self.assertTrue(any("Goal accepted" in line for line in output))
            self.assertTrue(any("WRITE_FILE" in line.upper() for line in output))


if __name__ == "__main__":
    unittest.main()
