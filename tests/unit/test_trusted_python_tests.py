import unittest
from pathlib import Path

from fam_os.verification.python import TrustedPythonTests, load_trusted_python_tests


FIXTURE = (
    Path(__file__).parents[1]
    / "fixtures"
    / "verification"
    / "stable_topological_sort_tests.py"
)


class TrustedPythonTestsTests(unittest.TestCase):
    def test_loads_verifier_owned_bundle(self) -> None:
        bundle = load_trusted_python_tests(FIXTURE, "stable-toposort.v1")
        self.assertEqual(bundle.bundle_id, "stable-toposort.v1")
        self.assertIn("cycle must raise", bundle.source)

    def test_rejects_invalid_trusted_test_syntax(self) -> None:
        with self.assertRaises(SyntaxError):
            TrustedPythonTests("broken.v1", "def broken(:")


if __name__ == "__main__":
    unittest.main()
