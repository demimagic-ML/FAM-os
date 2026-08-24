import base64
import hashlib
import os
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from fam_os.fabric import (
    PersistentDeviceIdentityStore,
    RemoteContextSensitivity,
    RemoteRawContextFragment,
    RemoteRawContextKind,
    RemoteTaskDescriptor,
    create_remote_context,
    create_remote_context_receipt,
    remote_context_content,
    verify_remote_context,
    verify_remote_context_receipt,
)

NOW = datetime(2026, 7, 17, 13, tzinfo=UTC)


class RemoteContextContractTests(unittest.TestCase):
    def test_exact_unicode_bytes_signatures_and_receipt_are_bound(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sender = _credentials(root / "sender", "Sender")
            receiver = _credentials(root / "receiver", "Receiver")
            fragment = _fragment("prompt", RemoteRawContextKind.PROMPT, "Analyze café 🚀")
            context = create_remote_context(
                sender, context_id="context-1", request_id="request-1",
                receiver_device_id=receiver.identity.device_id,
                target_expert_id="expert.code", purpose_id="assist",
                workspace_id="workspace:test",
                sensitivity=RemoteContextSensitivity.PRIVATE,
                descriptor=_descriptor(), raw_fragments=(fragment,), issued_at=NOW,
            )
            payload = remote_context_content(context)
            self.assertEqual(len(payload), context.content_bytes)
            self.assertEqual(hashlib.sha256(payload).hexdigest(), context.content_sha256)
            self.assertIn("café 🚀".encode(), payload)
            verify_remote_context(context, sender.identity, NOW)

            receipt = create_remote_context_receipt(receiver, context, NOW)
            verify_remote_context_receipt(receipt, context, receiver.identity)
            with self.assertRaisesRegex(ValueError, "differs"):
                verify_remote_context_receipt(
                    receipt, replace(context, request_id="request-2"), receiver.identity,
                )

    def test_invalid_exact_byte_evidence_and_signature_cannot_be_constructed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sender = _credentials(root / "sender", "Sender")
            receiver = _credentials(root / "receiver", "Receiver")
            context = create_remote_context(
                sender, context_id="context-1", request_id="request-1",
                receiver_device_id=receiver.identity.device_id,
                target_expert_id="expert.code", purpose_id="assist",
                workspace_id="workspace:test",
                sensitivity=RemoteContextSensitivity.PRIVATE,
                descriptor=_descriptor(), raw_fragments=(), issued_at=NOW,
            )
            with self.assertRaisesRegex(ValueError, "exact-byte"):
                replace(context, content_sha256="0" * 64)
            signature = bytearray(base64.b64decode(context.signature_base64))
            signature[0] ^= 1
            tampered = replace(
                context, signature_base64=base64.b64encode(signature).decode(),
            )
            with self.assertRaisesRegex(ValueError, "signature"):
                verify_remote_context(tampered, sender.identity, NOW)
            with self.assertRaisesRegex(ValueError, "signature"):
                replace(context, signature_base64="")


def _credentials(root: Path, name: str):
    return PersistentDeviceIdentityStore(
        root / "fabric/identity", os.geteuid(), now=lambda: NOW,
    ).resolve(name)


def _descriptor() -> RemoteTaskDescriptor:
    return RemoteTaskDescriptor("intent.code", ("code.generate",), "verified", 4096)


def _fragment(
    identity: str, kind: RemoteRawContextKind, content: str,
) -> RemoteRawContextFragment:
    encoded = content.encode()
    return RemoteRawContextFragment(
        identity, kind, hashlib.sha256(("source:" + identity).encode()).hexdigest(),
        content, hashlib.sha256(encoded).hexdigest(),
    )


if __name__ == "__main__":
    unittest.main()
