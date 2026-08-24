import base64
import tempfile
import unittest
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

from cryptography.hazmat.primitives import hashes

from fam_os.fabric import (
    RemoteContextSensitivity,
    RemoteExecutionStatus,
    RemoteRawContextKind,
    create_capability_declaration,
    create_remote_context,
    create_remote_context_receipt,
    create_remote_execution_request,
    create_remote_execution_result,
    verify_remote_execution_request,
    verify_remote_execution_result,
)
from fam_os.telemetry import InferenceMetrics
from fam_os.core.production import ModelIntent
from fam_os.product.remote_execution_planner import ProductRemoteExecutionPlanner
from tests.unit.test_remote_context import (
    NOW,
    _credentials,
    _descriptor,
    _fragment,
)


class RemoteExecutionContractTests(unittest.TestCase):
    def test_media_route_is_denied_until_binary_context_has_explicit_authority(self):
        authority = object()
        with self.assertRaisesRegex(PermissionError, "binary-context"):
            ProductRemoteExecutionPlanner(None).plan(
                "instance", "request", ModelIntent.MEDIA, authority,
                verification_required=True,
            )

    def test_signed_request_and_complete_result_bind_every_identity_and_bound(self):
        with tempfile.TemporaryDirectory() as temporary:
            sender, receiver, request, receipt = _request(Path(temporary))
            verify_remote_execution_request(request, sender.identity)
            metrics = InferenceMetrics("test:q4", 1.0, 0.1, 10, 2, 2.0)
            result = create_remote_execution_result(
                receiver, request, receipt, _fingerprint(sender),
                status=RemoteExecutionStatus.COMPLETED, content="READY",
                failure_code=None, metrics=metrics, started_at=NOW,
                completed_at=NOW + timedelta(seconds=1),
            )
            verify_remote_execution_result(
                result, request, receiver.identity, _fingerprint(sender),
            )

            with self.assertRaisesRegex(ValueError, "differs from request"):
                verify_remote_execution_result(
                    result, request, receiver.identity, "0" * 64,
                )
            oversized = create_remote_execution_result(
                receiver, request, receipt, _fingerprint(sender),
                status=RemoteExecutionStatus.COMPLETED, content="x" * 4097,
                failure_code=None,
                metrics=InferenceMetrics("test:q4", 1, 0, 10, 1024),
                started_at=NOW, completed_at=NOW,
            )
            with self.assertRaisesRegex(ValueError, "exceeds authorized output"):
                verify_remote_execution_result(
                    oversized, request, receiver.identity, _fingerprint(sender),
                )

    def test_signature_mutation_and_cross_identity_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sender, receiver, request, receipt = _request(root)
            other = _credentials(root / "other", "Other")
            with self.assertRaisesRegex(ValueError, "sender differs"):
                verify_remote_execution_request(request, other.identity)
            with self.assertRaisesRegex(ValueError, "signature"):
                verify_remote_execution_request(
                    replace(request, signature_base64=_mutate(request.signature_base64)),
                    sender.identity,
                )
            result = create_remote_execution_result(
                receiver, request, receipt, _fingerprint(sender),
                status=RemoteExecutionStatus.FAILED, content=None,
                failure_code="remote.runtime.failed", metrics=None,
                started_at=NOW, completed_at=NOW,
            )
            with self.assertRaisesRegex(ValueError, "signature"):
                verify_remote_execution_result(
                    replace(result, signature_base64=_mutate(result.signature_base64)),
                    request, receiver.identity, _fingerprint(sender),
                )


def _request(root):
    sender = _credentials(root / "sender", "Sender")
    receiver = _credentials(root / "receiver", "Receiver")
    context = create_remote_context(
        sender, context_id="remote-context", request_id="remote-request",
        receiver_device_id=receiver.identity.device_id,
        target_expert_id="expert.code", purpose_id="assist",
        workspace_id="workspace:test",
        sensitivity=RemoteContextSensitivity.PRIVATE,
        descriptor=_descriptor(),
        raw_fragments=(
            _fragment("prompt", RemoteRawContextKind.PROMPT, "Write the answer"),
        ),
        issued_at=NOW,
    )
    capability = create_capability_declaration(
        receiver, declaration_id="remote-capability", expert_id="expert.code",
        model_ref="test:q4", expert_tier="specialist",
        capability_ids=("code.generate",),
        maximum_context_bytes=8192, manifest_sha256="a" * 64, revision=1,
        issued_at=NOW, expires_at=NOW + timedelta(hours=1),
    )
    request = create_remote_execution_request(
        sender, execution_id="remote-execution", plan_id="remote-plan",
        context=context, capability=capability, context_tokens=2048,
        maximum_output_tokens=1024, json_output=False, temperature=0.2,
    )
    receipt = create_remote_context_receipt(receiver, context, NOW)
    return sender, receiver, request, receipt


def _fingerprint(credentials):
    return credentials.tls_certificate.fingerprint(hashes.SHA256()).hex()


def _mutate(value):
    raw = bytearray(base64.b64decode(value))
    raw[0] ^= 1
    return base64.b64encode(raw).decode()


if __name__ == "__main__":
    unittest.main()
