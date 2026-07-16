import unittest

from fam_os.adapters.language_tools import TemporaryToolchainVerifier, ToolGate
from fam_os.verification import LanguageGateStatus


class LanguageToolVerifierTests(unittest.TestCase):
    def test_candidate_execution_requires_explicit_trusted_fixture_mode(self) -> None:
        verifier = TemporaryToolchainVerifier(
            "javascript", "js", "test", (
                ToolGate("javascript.tests", ("/usr/bin/node", "{candidate}"), True),
            )
        )
        report = verifier.verify("js-1", "process.exit(0)")
        self.assertEqual(LanguageGateStatus.ERROR, report.gates[0].status)
        self.assertFalse(report.passed)

    def test_missing_tool_is_error(self) -> None:
        verifier = TemporaryToolchainVerifier(
            "test", "txt", "test", (ToolGate("compile", ("/missing/tool",)),)
        )
        self.assertEqual(
            LanguageGateStatus.ERROR, verifier.verify("missing", "x").gates[0].status
        )


if __name__ == "__main__":
    unittest.main()
