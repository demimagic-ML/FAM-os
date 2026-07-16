import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from fam_os.core.admission import (
    InMemoryRequestAuthorityRegistry,
    InMemoryRequestReplayRegistry,
    RequestAdmissionOutcome,
    RequestAdmissionService,
    RequestAuthorityGrant,
    RequestIdentity,
)
from fam_os.core.contracts import FailureCategory, TaskRequest


NOW = datetime(2026, 7, 16, 16, tzinfo=timezone.utc)


def authority(**changes):
    values = {
        "authority_ref": "authority-1",
        "principal_id": "principal-1",
        "session_id": "session-1",
        "granted_capabilities": ("files.read", "code.execute"),
        "issued_at": NOW - timedelta(minutes=5),
        "expires_at": NOW + timedelta(hours=1),
        "revoked_at": None,
    }
    values.update(changes)
    return RequestAuthorityGrant(**values)


def identity(**changes):
    values = {
        "principal_id": "principal-1",
        "session_id": "session-1",
        "authority_ref": "authority-1",
    }
    values.update(changes)
    return RequestIdentity(**values)


def service(grant=None, replay=None):
    registry = InMemoryRequestAuthorityRegistry(
        () if grant is False else (grant or authority(),)
    )
    return RequestAdmissionService(
        registry, replay or InMemoryRequestReplayRegistry(),
        clock=lambda: NOW,
        admission_id_factory=lambda: "admission-1",
        error_id_factory=lambda: "error-1",
    )


class RequestAdmissionTests(unittest.TestCase):
    def test_admits_with_exact_least_privilege_permission_context(self):
        request = TaskRequest(
            "request-1", "Read the selected file", ("files.read",)
        )

        outcome = service().admit(request, identity())

        self.assertTrue(outcome.accepted)
        self.assertIsNone(outcome.failure)
        admitted = outcome.admitted
        self.assertEqual("admission-1", admitted.admission_id)
        self.assertEqual(("files.read",), admitted.permission.authorized_capabilities)
        self.assertEqual("principal-1", admitted.permission.principal_id)
        self.assertEqual(authority().expires_at, admitted.permission.valid_until)
        self.assertEqual(
            ("code.execute", "files.read"), authority().granted_capabilities
        )

    def test_missing_or_mismatched_authority_is_indistinguishable(self):
        request = TaskRequest("request-1", "Read", ("files.read",))
        outcomes = (
            service(grant=False).admit(request, identity()),
            service().admit(request, identity(principal_id="principal-2")),
            service().admit(request, identity(session_id="session-2")),
        )
        self.assertTrue(all(not item.accepted for item in outcomes))
        self.assertEqual(
            {"admission.authority_denied"},
            {item.failure.code for item in outcomes},
        )
        self.assertEqual(
            {"Request authority is unavailable or invalid."},
            {item.failure.safe_message for item in outcomes},
        )

    def test_inactive_authority_is_rejected(self):
        grants = (
            authority(expires_at=NOW),
            authority(issued_at=NOW + timedelta(minutes=1),
                      expires_at=NOW + timedelta(hours=1)),
            authority(revoked_at=NOW - timedelta(seconds=1)),
        )
        for grant in grants:
            with self.subTest(grant=grant):
                outcome = service(grant).admit(
                    TaskRequest("request-1", "Read"), identity()
                )
                self.assertFalse(outcome.accepted)
                self.assertEqual("admission.authority_inactive", outcome.failure.code)

    def test_missing_capability_is_linked_in_permission_failure(self):
        request = TaskRequest(
            "request-1", "Write", ("files.write", "code.execute")
        )

        outcome = service().admit(request, identity())

        self.assertFalse(outcome.accepted)
        self.assertEqual(FailureCategory.PERMISSION_DENIED, outcome.failure.category)
        self.assertEqual("admission.capability_denied", outcome.failure.code)
        self.assertEqual("files.write", outcome.failure.capability_id)

    def test_successful_request_id_cannot_be_replayed(self):
        admission = service()
        request = TaskRequest("request-1", "Read", ("files.read",))

        first = admission.admit(request, identity())
        second = admission.admit(request, identity())

        self.assertTrue(first.accepted)
        self.assertFalse(second.accepted)
        self.assertEqual("admission.request_replayed", second.failure.code)
        self.assertEqual(FailureCategory.INVALID_REQUEST, second.failure.category)

    def test_denial_does_not_burn_request_id(self):
        replay = InMemoryRequestReplayRegistry()
        denied = service(replay=replay).admit(
            TaskRequest("request-1", "Write", ("files.write",)), identity()
        )
        accepted = service(replay=replay).admit(
            TaskRequest("request-1", "Read", ("files.read",)), identity()
        )
        self.assertFalse(denied.accepted)
        self.assertTrue(accepted.accepted)

    def test_replay_reservation_is_atomic_under_concurrency(self):
        registry = InMemoryRequestReplayRegistry()
        with ThreadPoolExecutor(max_workers=8) as pool:
            outcomes = tuple(pool.map(registry.reserve, ("request-1",) * 32))
        self.assertEqual(1, sum(outcomes))

    def test_admission_contract_rejects_ambiguous_outcome(self):
        with self.assertRaises(ValueError):
            RequestAdmissionOutcome("request-1")

    def test_authority_and_request_contracts_reject_malformed_input(self):
        with self.assertRaises(ValueError):
            authority(issued_at=NOW.replace(tzinfo=None))
        with self.assertRaises(ValueError):
            identity(principal_id="principal\nforged")
        with self.assertRaises(ValueError):
            TaskRequest("request\nforged", "Read")
        with self.assertRaises(ValueError):
            TaskRequest("request-1", "x" * 131_073)
        with self.assertRaises(ValueError):
            TaskRequest(
                "request-1", "Read", tuple(f"capability-{i}" for i in range(65))
            )


if __name__ == "__main__":
    unittest.main()
