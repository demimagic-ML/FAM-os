import hashlib
import os
import tempfile
import unittest
from pathlib import Path

from fam_os.fabric import (
    PeerManagementOperation,
    PeerManagementRequest,
    RemoteContextDirection,
    RemoteContextSensitivity,
    RemoteContextSendRequest,
    RemotePrivacyPolicy,
    RemoteRawContextFragment,
    RemoteRawContextKind,
    RemoteTaskDescriptor,
)
from fam_os.product.composition.peer_service import ProductPeerService, ProductPeerSettings
from fam_os.product.peer_context import ProductPeerContextService
from fam_os.product.peer_management import ProductPeerManagement
from tests.integration.test_product_peer_management import (
    _approvals,
    _capabilities,
    _storage,
    _unused_port,
)


class ProductPeerContextTests(unittest.TestCase):
    def test_context_is_fail_closed_exact_and_content_free_at_rest(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            server_root, desktop_root = root / "server", root / "desktop"
            port = _unused_port()
            server_creds, _, server_approval, desktop_approval = _approvals(
                server_root, desktop_root, port,
            )
            server_storage, server_repositories = _storage(server_root)
            desktop_storage, desktop_repositories = _storage(desktop_root)
            server_repositories.peer_enrollments.enroll(server_approval)
            desktop_record = desktop_repositories.peer_enrollments.enroll(desktop_approval)
            server = ProductPeerService(
                ProductPeerSettings(server_root, "Server", "127.0.0.1", port),
                server_repositories.peer_enrollments, os.geteuid(), _capabilities,
                server_repositories.peer_context,
            )
            desktop = ProductPeerService(
                ProductPeerSettings(desktop_root, "Desktop"),
                desktop_repositories.peer_enrollments, os.geteuid(),
                context_repository=desktop_repositories.peer_context,
            )
            try:
                server.start()
                desktop.start()
                context_service = ProductPeerContextService(
                    desktop_repositories.peer_enrollments,
                    desktop_repositories.peer_state,
                    desktop_repositories.peer_context,
                    desktop, str(os.geteuid()),
                )
                management = ProductPeerManagement(
                    desktop_repositories.peer_enrollments,
                    desktop_repositories.peer_state,
                    desktop, str(os.geteuid()), context=context_service,
                )
                peer = management.probe(desktop_record.enrollment_id, "probe-context")
                declaration = peer.capabilities[0]

                denied = _request(
                    "context-no-policy", desktop_record.enrollment_id,
                    declaration.declaration_id,
                )
                with self.assertRaisesRegex(PermissionError, "defaults to denied"):
                    management.send_context(denied)
                self.assertEqual((), server_repositories.peer_context.all())

                policy = _policy(server_creds.identity.device_id, raw=False)
                management.apply_control(PeerManagementRequest(
                    "privacy-context-1", str(os.geteuid()),
                    PeerManagementOperation.SET_PRIVACY,
                    desktop_record.enrollment_id, 0, True, "owner.context", policy,
                ))
                accepted = management.send_context(_request(
                    "context-descriptor", desktop_record.enrollment_id,
                    declaration.declaration_id,
                ))
                self.assertEqual(RemoteContextDirection.OUTBOUND, accepted.direction)
                self.assertEqual((), accepted.raw_fragment_sha256)
                self.assertEqual(1, len(server_repositories.peer_context.all()))

                for invalid in (
                    {"declaration_id": "capability-missing"},
                    {"target_expert_id": "expert.other"},
                    {"capability_ids": ("math.solve",)},
                ):
                    request = _request(
                        "denied-capability-" + str(len(invalid)) + "-" + next(iter(invalid)),
                        desktop_record.enrollment_id,
                        invalid.get("declaration_id", declaration.declaration_id),
                        target_expert_id=invalid.get("target_expert_id", "expert.code"),
                        capability_ids=invalid.get("capability_ids", ("code.generate",)),
                    )
                    with self.assertRaisesRegex(PermissionError, "capability"):
                        management.send_context(request)

                sentinels = []
                for kind in RemoteRawContextKind:
                    sentinel = f"NEVER-CROSS-{kind.value}-8f9c1"
                    sentinels.append(sentinel)
                    request = _request(
                        f"denied-{kind.value.replace('_', '-')}",
                        desktop_record.enrollment_id, declaration.declaration_id,
                        (_fragment(kind.value.replace("_", "-"), kind, sentinel),),
                        confirmed=True,
                    )
                    with self.assertRaisesRegex(PermissionError, "raw-content"):
                        management.send_context(request)
                self.assertEqual(1, len(server_repositories.peer_context.all()))
                self.assertEqual(1, len(desktop_repositories.peer_context.all()))

                for changed, pattern in (
                    ({"purpose_id": "unapproved"}, "privacy.purpose"),
                    ({"workspace_id": "workspace:other"}, "privacy.workspace"),
                    ({"sensitivity": RemoteContextSensitivity.RESTRICTED}, "privacy.sensitivity"),
                ):
                    request = _request(
                        "denied-" + pattern.replace(".", "-"),
                        desktop_record.enrollment_id, declaration.declaration_id,
                        **changed,
                    )
                    with self.assertRaisesRegex(PermissionError, pattern):
                        management.send_context(request)

                with self.assertRaisesRegex(RuntimeError, "revision changed"):
                    management.send_context(_request(
                        "denied-stale-policy", desktop_record.enrollment_id,
                        declaration.declaration_id, expected_privacy_revision=2,
                    ))
                with self.assertRaisesRegex(PermissionError, "confirmation"):
                    _request(
                        "denied-unconfirmed", desktop_record.enrollment_id,
                        declaration.declaration_id,
                        (_fragment("unconfirmed", RemoteRawContextKind.PROMPT, "private"),),
                    )

                management.apply_control(PeerManagementRequest(
                    "privacy-context-2", str(os.geteuid()),
                    PeerManagementOperation.SET_PRIVACY,
                    desktop_record.enrollment_id, 1, True, "owner.raw-context",
                    _policy(server_creds.identity.device_id, raw=True),
                ))
                oversized_policy = "DENIED-POLICY-BYTES-4c2e1" + "x" * 5000
                sentinels.append(oversized_policy)
                with self.assertRaisesRegex(PermissionError, "context-bytes"):
                    management.send_context(_request(
                        "denied-policy-bytes", desktop_record.enrollment_id,
                        declaration.declaration_id,
                        (_fragment(
                            "policy-bytes", RemoteRawContextKind.PROMPT,
                            oversized_policy,
                        ),),
                        confirmed=True, expected_privacy_revision=2,
                    ))
                allowed_sentinel = "ALLOWED-BUT-NOT-STORED-PRIVATE-f26a7"
                allowed_request = _request(
                    "context-raw", desktop_record.enrollment_id,
                    declaration.declaration_id,
                    (_fragment("raw-allowed", RemoteRawContextKind.PROMPT, allowed_sentinel),),
                    confirmed=True, expected_privacy_revision=2,
                )
                raw_evidence = management.send_context(allowed_request)
                self.assertEqual(1, len(raw_evidence.raw_fragment_sha256))
                self.assertEqual(raw_evidence, management.send_context(allowed_request))
                with self.assertRaisesRegex(ValueError, "identity was reused"):
                    management.send_context(_request(
                        "context-raw", desktop_record.enrollment_id,
                        declaration.declaration_id, purpose_id="another-purpose",
                        expected_privacy_revision=2,
                    ))

                management.apply_control(PeerManagementRequest(
                    "privacy-context-3", str(os.geteuid()),
                    PeerManagementOperation.SET_PRIVACY,
                    desktop_record.enrollment_id, 2, True, "owner.large-context",
                    _policy(
                        server_creds.identity.device_id, raw=True,
                        maximum_context_bytes=16_000,
                    ),
                ))
                oversized_capability = "DENIED-CAPABILITY-BYTES-6ad91" + "y" * 9000
                sentinels.append(oversized_capability)
                with self.assertRaisesRegex(PermissionError, "capability ceiling"):
                    management.send_context(_request(
                        "denied-capability-bytes", desktop_record.enrollment_id,
                        declaration.declaration_id,
                        (_fragment(
                            "capability-bytes", RemoteRawContextKind.PROMPT,
                            oversized_capability,
                        ),),
                        confirmed=True, expected_privacy_revision=3,
                    ))
                self.assertEqual(2, len(server_repositories.peer_context.all()))
                self.assertEqual(2, len(desktop_repositories.peer_context.all()))

                for value in (*sentinels, allowed_sentinel):
                    self.assertNotIn(value.encode(), _all_file_bytes(root))
            finally:
                desktop.stop()
                server.stop()
                desktop_storage.stop()
                server_storage.stop()


def _request(
    request_id, enrollment_id, declaration_id, raw_fragments=(), *,
    confirmed=False, expected_privacy_revision=1, purpose_id="assist",
    workspace_id="workspace:test", sensitivity=RemoteContextSensitivity.PRIVATE,
    target_expert_id="expert.code", capability_ids=("code.generate",),
):
    return RemoteContextSendRequest(
        request_id, enrollment_id, target_expert_id, declaration_id,
        expected_privacy_revision, purpose_id, workspace_id, sensitivity,
        RemoteTaskDescriptor(
            "intent.code", capability_ids, "verified", 4096,
        ),
        raw_fragments, confirmed,
    )


def _fragment(identity, kind, content):
    return RemoteRawContextFragment(
        identity, kind, hashlib.sha256(("source:" + identity).encode()).hexdigest(),
        content, hashlib.sha256(content.encode()).hexdigest(),
    )


def _policy(device_id, *, raw, maximum_context_bytes=4096):
    return RemotePrivacyPolicy(
        str(os.geteuid()), (device_id,), ("assist",), ("workspace:test",),
        maximum_context_bytes, (RemoteContextSensitivity.PRIVATE,), raw,
    )


def _all_file_bytes(root):
    return b"".join(path.read_bytes() for path in root.rglob("*") if path.is_file())


if __name__ == "__main__":
    unittest.main()
