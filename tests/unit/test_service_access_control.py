import unittest
from datetime import datetime, timedelta, timezone

from fam_os.supervisor import (
    AccessApplicationEvidence,
    AccessEvidenceStatus,
    AccessMode,
    AccessResourceDescriptor,
    AccessResourceKind,
    InMemoryAccessGrantRegistry,
    InMemoryAccessResourceCatalog,
    InMemoryServiceOwnershipRegistry,
    OwnedService,
    ServiceAccessController,
    ServiceAccessGrant,
    ServiceDefinition,
    SupervisorAuthorizationError,
    SupervisorCallContext,
)


NOW = datetime(2026, 7, 16, tzinfo=timezone.utc)


class AllowAuthorizer:
    def require(self, context, capability, service_id) -> None:
        pass


class RecordingAccessAdapter:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.mismatch = False

    def grant(self, grant, resource) -> AccessApplicationEvidence:
        self.calls.append("grant")
        resource_id = "filesystem.wrong" if self.mismatch else resource.resource_id
        return AccessApplicationEvidence(
            grant.grant_id,
            grant.service_id,
            resource_id,
            "fake.access",
            AccessEvidenceStatus.GRANTED,
            NOW,
        )

    def revoke(self, grant, resource) -> AccessApplicationEvidence:
        self.calls.append("revoke")
        return AccessApplicationEvidence(
            grant.grant_id,
            grant.service_id,
            resource.resource_id,
            "fake.access",
            AccessEvidenceStatus.REVOKED,
            NOW,
        )


def context(principal: str = "principal") -> SupervisorCallContext:
    return SupervisorCallContext("request", principal, "session", "authority")


def grant(
    *,
    resource_id: str = "filesystem.models",
    kind: AccessResourceKind = AccessResourceKind.FILESYSTEM,
    mode: AccessMode = AccessMode.READ,
    expires_at: datetime = NOW + timedelta(hours=1),
) -> ServiceAccessGrant:
    return ServiceAccessGrant(
        "grant-1",
        "authority",
        "principal",
        "session",
        "fam-access-test",
        resource_id,
        kind,
        mode,
        NOW - timedelta(minutes=1),
        expires_at,
    )


class ServiceAccessControlTests(unittest.TestCase):
    def setUp(self) -> None:
        ownership = InMemoryServiceOwnershipRegistry()
        ownership.claim(
            OwnedService(
                "principal",
                "session",
                ServiceDefinition("fam-access-test", ("/usr/bin/true",)),
            )
        )
        catalog = InMemoryAccessResourceCatalog(
            (
                AccessResourceDescriptor(
                    "filesystem.models",
                    AccessResourceKind.FILESYSTEM,
                    (AccessMode.READ,),
                ),
                AccessResourceDescriptor(
                    "device.gpu-0",
                    AccessResourceKind.DEVICE,
                    (AccessMode.READ_WRITE,),
                ),
            )
        )
        self.grants = InMemoryAccessGrantRegistry()
        self.adapter = RecordingAccessAdapter()
        self.controller = ServiceAccessController(
            AllowAuthorizer(), ownership, catalog, self.grants, self.adapter
        )

    def test_grants_and_revokes_exact_allowlisted_scope(self) -> None:
        applied = self.controller.grant(context(), grant(), NOW)
        revoked = self.controller.revoke(context(), grant().grant_id, NOW)
        self.assertEqual(AccessEvidenceStatus.GRANTED, applied.status)
        self.assertEqual(AccessEvidenceStatus.REVOKED, revoked.status)
        self.assertTrue(self.grants.get(grant().grant_id).revoked)
        self.assertEqual(["grant", "revoke"], self.adapter.calls)

    def test_revoked_grant_id_cannot_be_reused(self) -> None:
        self.controller.grant(context(), grant(), NOW)
        self.controller.revoke(context(), grant().grant_id, NOW)
        with self.assertRaisesRegex(SupervisorAuthorizationError, "already used"):
            self.controller.grant(context(), grant(), NOW)
        self.assertEqual(["grant", "revoke"], self.adapter.calls)

    def test_raw_path_cannot_be_a_resource_identifier(self) -> None:
        with self.assertRaisesRegex(ValueError, "opaque"):
            AccessResourceDescriptor(
                "/home/private", AccessResourceKind.FILESYSTEM, (AccessMode.READ,)
            )

    def test_unknown_resource_expiry_and_wrong_owner_fail_before_adapter(self) -> None:
        cases = (
            (context(), grant(resource_id="filesystem.unknown"), NOW),
            (context(), grant(expires_at=NOW), NOW),
            (context("other"), grant(), NOW),
        )
        for call_context, access_grant, instant in cases:
            with self.subTest(grant=access_grant.resource_id, principal=call_context.principal_id):
                with self.assertRaises(SupervisorAuthorizationError):
                    self.controller.grant(call_context, access_grant, instant)
        self.assertEqual([], self.adapter.calls)

    def test_kind_or_mode_outside_allowlist_is_denied(self) -> None:
        with self.assertRaises(SupervisorAuthorizationError):
            self.controller.grant(
                context(), grant(mode=AccessMode.READ_WRITE), NOW
            )
        with self.assertRaises(SupervisorAuthorizationError):
            self.controller.grant(
                context(), grant(kind=AccessResourceKind.DEVICE), NOW
            )

    def test_mismatched_adapter_evidence_is_not_recorded(self) -> None:
        self.adapter.mismatch = True
        with self.assertRaisesRegex(SupervisorAuthorizationError, "mismatched"):
            self.controller.grant(context(), grant(), NOW)
        self.assertIsNone(self.grants.get(grant().grant_id))


if __name__ == "__main__":
    unittest.main()
