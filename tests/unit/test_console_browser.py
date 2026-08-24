import subprocess
import unittest
from unittest.mock import Mock, patch

from fam_os.adapters.linux.console_browser import XdgConsoleBrowser


class ConsoleBrowserTests(unittest.TestCase):
    def test_detaches_when_desktop_launcher_remains_attached(self):
        process = Mock()
        process.wait.side_effect = subprocess.TimeoutExpired("xdg-open", 0.25)
        with patch(
            "fam_os.adapters.linux.console_browser.subprocess.Popen",
            return_value=process,
        ) as popen:
            opened = XdgConsoleBrowser().open("http://127.0.0.1:8765/#token=secret")

        self.assertTrue(opened)
        popen.assert_called_once()
        self.assertTrue(popen.call_args.kwargs["start_new_session"])
        self.assertTrue(popen.call_args.kwargs["close_fds"])

    def test_rejects_immediate_launcher_failure(self):
        process = Mock()
        process.wait.return_value = 3
        with patch(
            "fam_os.adapters.linux.console_browser.subprocess.Popen",
            return_value=process,
        ):
            opened = XdgConsoleBrowser().open("http://127.0.0.1:8765/")

        self.assertFalse(opened)

    def test_rejects_missing_desktop_launcher(self):
        with patch(
            "fam_os.adapters.linux.console_browser.subprocess.Popen",
            side_effect=FileNotFoundError,
        ):
            opened = XdgConsoleBrowser().open("http://127.0.0.1:8765/")

        self.assertFalse(opened)


if __name__ == "__main__":
    unittest.main()
