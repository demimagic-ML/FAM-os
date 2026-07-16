import unittest

from fam_os.fabric.privacy import (
    RemoteContextRequest, RemoteContextSensitivity, RemotePrivacyEvaluator,
    RemotePrivacyPolicy,
)


class RemotePrivacyPolicyTests(unittest.TestCase):
    def test_exact_policy_allows_redacted_bounded_context(self):
        policy = RemotePrivacyPolicy("owner", ("server",), ("assist",), ("project",),
                                     1000, (RemoteContextSensitivity.PRIVATE,), False)
        request = RemoteContextRequest("owner", "server", "assist", "project",
                                       RemoteContextSensitivity.PRIVATE, 100, False)
        self.assertTrue(RemotePrivacyEvaluator().decide(policy, request).allowed)

    def test_raw_cross_workspace_and_oversize_are_denied(self):
        policy = RemotePrivacyPolicy("owner", ("server",), ("assist",), ("project",),
                                     100, (RemoteContextSensitivity.PRIVATE,), False)
        request = RemoteContextRequest("owner", "server", "assist", "other",
                                       RemoteContextSensitivity.PRIVATE, 101, True)
        decision = RemotePrivacyEvaluator().decide(policy, request)
        self.assertEqual(("privacy.workspace", "privacy.context-bytes", "privacy.raw-content"),
                         decision.reason_codes)


if __name__ == "__main__":
    unittest.main()
