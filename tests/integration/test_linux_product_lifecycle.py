import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from fam_os.product.linux_installation import LinuxInstallation


class LinuxProductLifecycleTests(unittest.TestCase):
    def test_install_diagnose_repair_update_and_remove(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source" / "fam_os"
            shutil.copytree(Path("src/fam_os"), source)
            installation = LinuxInstallation(root / "installed" / "fam-os")
            self.assertTrue(installation.install(source, "v1").healthy)
            self.assertTrue(installation.diagnose().healthy)
            help_result = subprocess.run(
                (str(installation.prefix / "bin" / "fam-service"), "--help"),
                check=True, capture_output=True, text=True,
            )
            self.assertIn("local product service", help_result.stdout)
            launcher = installation.prefix / "bin" / "fam-shell"
            launcher.write_text("damaged")
            self.assertFalse(installation.diagnose().healthy)
            self.assertTrue(installation.repair(source).healthy)
            (source / "__init__.py").write_text("VERSION = 2\n")
            self.assertTrue(installation.update(source, "v2").healthy)
            self.assertEqual(installation.diagnose().release_id, "v2")
            installation.remove()
            self.assertFalse(installation.prefix.exists())

    def test_remove_refuses_unmarked_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            prefix = Path(directory, "not-fam")
            prefix.mkdir()
            with self.assertRaises(FileNotFoundError):
                LinuxInstallation(prefix).remove()


if __name__ == "__main__":
    unittest.main()
