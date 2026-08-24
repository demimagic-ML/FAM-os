import tempfile
import unittest
from pathlib import Path

from fam_os.adapters.integration.retained_artifacts import capture_retained_artifacts


class IntegrationRetainedArtifactTests(unittest.TestCase):
    def test_regular_declared_artifact_is_content_bound(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "reports").mkdir()
            (root / "reports/result.json").write_bytes(b'{"passed":true}\n')

            values = capture_retained_artifacts(root, ("reports/result.json",), 64)

            self.assertEqual("reports/result.json", values[0].relative_path)
            self.assertEqual(64, len(values[0].sha256))

    def test_symlink_missing_internal_and_budget_escape_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "large").write_bytes(b"12345")
            (root / "link").symlink_to(root / "large")
            (root / ".fam/integration").mkdir(parents=True)
            (root / ".fam/integration/state").write_text("secret")

            for path, message in (
                ("link", "symbolic"), ("missing", "missing"),
                (".fam/integration/state", "internal"), ("large", "budget"),
            ):
                with self.subTest(path=path), self.assertRaisesRegex(PermissionError, message):
                    capture_retained_artifacts(root, (path,), 4)


if __name__ == "__main__":
    unittest.main()
