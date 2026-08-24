import unittest

from fam_os.core.engineering.diagnostic_redaction import (
    DeterministicDiagnosticTextSanitizer,
    sanitize_diagnostic_evidence,
    sanitize_diagnostic_feedback,
)


class EngineeringDiagnosticRedactionTests(unittest.TestCase):
    def test_sandbox_and_model_redaction_share_fail_closed_secret_policy(self):
        raw = (
            "\x1b[31mfailed\x1b[0m at /home/owner/private/app.py:7 "
            "Authorization: Bearer top-secret-token\x00"
        )
        sanitized = DeterministicDiagnosticTextSanitizer().sanitize(raw, 2_048)
        text = sanitized.content.decode()

        self.assertIn("failed at [REDACTED_PATH]:7", text)
        self.assertIn("[REDACTED]", text)
        self.assertNotIn("owner", text)
        self.assertNotIn("top-secret-token", text)
        self.assertNotIn("\x1b", text)
        self.assertTrue(
            sanitized.sanitizer_evidence_id.startswith(
                "diagnostic-text-sanitizer-v2:"
            )
        )

        feedback = sanitize_diagnostic_feedback((raw,))
        self.assertEqual(1, len(feedback))
        self.assertTrue(feedback[0].startswith("[REDACTED_DIAGNOSTIC sha256="))
        self.assertNotIn("failed", feedback[0])
        self.assertNotIn("top-secret-token", feedback[0])

    def test_feedback_is_deterministically_bounded_and_control_free(self):
        values = tuple(
            f"diagnostic-{index}=\x1b[32m{'x' * 3000}\x1b[0m\x07"
            for index in range(20)
        )
        first = sanitize_diagnostic_feedback(
            values, maximum_items=4, maximum_item_bytes=256,
            maximum_total_bytes=800,
        )
        second = sanitize_diagnostic_feedback(
            values, maximum_items=4, maximum_item_bytes=256,
            maximum_total_bytes=800,
        )

        self.assertEqual(first, second)
        self.assertLessEqual(len(first), 4)
        self.assertLessEqual(sum(len(item.encode()) for item in first), 800)
        self.assertTrue(any("TRUNCATED" in item for item in first))
        self.assertNotIn("\x1b", "".join(first))
        self.assertNotIn("\x07", "".join(first))

    def test_private_key_feedback_is_digest_only(self):
        value = (
            "-----BEGIN PRIVATE KEY-----\nsecret-material\n"
            "-----END PRIVATE KEY-----"
        )
        feedback = sanitize_diagnostic_feedback((value,))
        self.assertEqual(1, len(feedback))
        self.assertIn("REDACTED_DIAGNOSTIC", feedback[0])
        self.assertNotIn("secret-material", feedback[0])

    def test_persisted_evidence_never_contains_secret_or_owner_path(self):
        secret = sanitize_diagnostic_evidence("failure token=credential-value")
        path = sanitize_diagnostic_evidence(
            "failure at /home/owner/private/project/app.py:10"
        )

        self.assertIn("REDACTED_DIAGNOSTIC", secret)
        self.assertNotIn("credential-value", secret)
        self.assertEqual("failure at [REDACTED_PATH]:10", path)


if __name__ == "__main__":
    unittest.main()
