import unittest
from unittest.mock import patch

from fam_os.product.fam_cli import main


class FamCliTests(unittest.TestCase):
    def test_no_arguments_open_the_tui_and_console_remains_explicit(self):
        with patch("fam_os.product.fam_cli.fam_os_main", return_value=0) as delegate:
            self.assertEqual(main([]), 0)
            delegate.assert_called_once_with(
                ["agent", "--interactive", "--source", "fam-tui"],
            )
        with patch("fam_os.product.fam_cli.fam_os_main", return_value=0) as delegate:
            self.assertEqual(main(["console", "--port", "9000"]), 0)
            delegate.assert_called_once_with(["console", "--port", "9000"])

    def test_goal_and_plain_prompts_use_the_agent_launcher(self):
        with patch("fam_os.product.fam_cli.fam_os_main", return_value=0) as delegate:
            self.assertEqual(main(["goal"]), 0)
            delegate.assert_called_once_with(
                [
                    "agent",
                    "--interactive",
                    "--goal",
                    "--source",
                    "fam-goal-tui",
                ]
            )
        with patch("fam_os.product.fam_cli.fam_os_main", return_value=0) as delegate:
            self.assertEqual(main(["goal", "build", "it"]), 0)
            delegate.assert_called_once_with(["agent", "--goal", "build", "it"])
        with patch("fam_os.product.fam_cli.fam_os_main", return_value=0) as delegate:
            self.assertEqual(main(["explain", "this"]), 0)
            delegate.assert_called_once_with(["agent", "explain", "this"])


if __name__ == "__main__":
    unittest.main()
