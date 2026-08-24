import unittest
from dataclasses import replace
from datetime import timedelta

from fam_os.product.owner_engineering_authentication import (
    OwnerEngineeringAuthenticationRegistry,
    ProductOwnerAuthorityVerifier,
    break_glass_authentication_digest,
)
from tests.contract.schema_engineering_fixtures import (
    NOW,
    engineering_grant_schema_values,
)


class OwnerEngineeringAuthenticationTests(unittest.TestCase):
    def setUp(self) -> None:
        (
            self.grant, self.approval, _request, _authorization,
            self.challenge, self.decision, _execution,
        ) = engineering_grant_schema_values()
        self.now = NOW
        identifiers = iter(("grant-context", "break-glass-context"))
        self.registry = OwnerEngineeringAuthenticationRegistry(
            self.grant.owner_id, lambda: self.now, lambda: next(identifiers),
        )
        self.verifier = ProductOwnerAuthorityVerifier(self.registry)

    def test_exact_grant_context_is_single_use(self) -> None:
        context = self.registry.issue(
            self.grant.owner_id, "engineering-grant",
            self.approval.grant_sha256,
        )
        approval = replace(self.approval, authentication_context_id=context.context_id)
        self.assertTrue(self.verifier.verify_grant(approval, self.approval.grant_sha256))
        self.assertFalse(self.verifier.verify_grant(approval, self.approval.grant_sha256))

    def test_break_glass_context_binds_exact_consequences(self) -> None:
        digest = break_glass_authentication_digest(self.challenge, self.decision)
        context = self.registry.issue(
            self.grant.owner_id, "engineering-break-glass", digest,
        )
        decision = replace(self.decision, authentication_context_id=context.context_id)
        self.assertTrue(self.verifier.verify_break_glass(self.challenge, decision))

    def test_mismatch_or_expiry_consumes_without_authorizing(self) -> None:
        context = self.registry.issue(
            self.grant.owner_id, "engineering-grant",
            self.approval.grant_sha256,
        )
        approval = replace(self.approval, authentication_context_id=context.context_id)
        self.assertFalse(self.verifier.verify_grant(approval, "0" * 64))
        other = self.registry.issue(
            self.grant.owner_id, "engineering-grant",
            self.approval.grant_sha256,
        )
        self.now += timedelta(minutes=3)
        expired = replace(approval, authentication_context_id=other.context_id)
        self.assertFalse(self.verifier.verify_grant(expired, self.approval.grant_sha256))

    def test_transport_bound_context_cannot_cross_console_sessions(self) -> None:
        context = self.registry.issue(
            self.grant.owner_id, "engineering-grant",
            self.approval.grant_sha256, "console-session-1",
        )
        self.assertTrue(self.registry.belongs_to_session(
            context.context_id, "console-session-1",
        ))
        self.assertFalse(self.registry.belongs_to_session(
            context.context_id, "console-session-2",
        ))


if __name__ == "__main__":
    unittest.main()
