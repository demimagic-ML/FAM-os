import subprocess
import sys
import unittest


class AdapterImportOrderTests(unittest.TestCase):
    def test_hyprland_can_be_imported_before_linux_discovery(self):
        result = subprocess.run(
            (
                sys.executable, "-c",
                "from fam_os.adapters.hyprland.events import HyprlandEventStream; "
                "from fam_os.adapters.linux import LinuxApplicationDiscovery; "
                "assert HyprlandEventStream and LinuxApplicationDiscovery",
            ),
            check=False, capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
