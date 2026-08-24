"""Authenticated remote inference client implementing the Core execution port."""

from __future__ import annotations

import hashlib

from cryptography.hazmat.primitives import hashes

from fam_os.core.ports.inference import InferenceResponse
from fam_os.core.production.generation_input import AuthenticatedRemoteInference
from fam_os.fabric import (
    MutualTlsPeerClient,
    PairedPeerTrust,
    RemoteContextSendRequest,
    RemoteExecutionResult,
    RemoteExecutionStatus,
    create_remote_execution_request,
    verify_remote_context_receipt,
    verify_remote_execution_result,
)
from fam_os.schemas import dumps_document, loads_document


class ProductRemoteExecutionClient:
    def __init__(
        self, context_service, enrollments, peer_service, owner_id: str,
        *, client_factory=None,
    ) -> None:
        if not owner_id.strip():
            raise ValueError("remote execution owner is invalid")
        self._context = context_service
        self._enrollments = enrollments
        self._peer_service = peer_service
        self._owner_id = owner_id
        self._client_factory = client_factory or (
            lambda trust: MutualTlsPeerClient(
                trust, io_timeout_seconds=300.0,
            )
        )

    def execute(self, record, prepared) -> AuthenticatedRemoteInference:
        plan = record.remote_plan
        if plan is None or not record.remote_attempt_consumed:
            raise ValueError("remote execution attempt was not durably reserved")
        fragments = prepared.remote_fragments()
        context_request_id = _context_request_id(record.request_id)
        context_request = RemoteContextSendRequest(
            context_request_id, plan.enrollment_id, plan.expert_id,
            plan.capability_declaration_id, plan.expected_privacy_revision,
            plan.purpose_id, plan.workspace_id, plan.sensitivity,
            plan.descriptor, fragments, True,
        )
        authorized = self._context.prepare(context_request)
        if (
            authorized.declaration.declaration_id
            != plan.capability_declaration_id
            or authorized.declaration.model_ref != plan.model_ref
            or authorized.declaration.expert_tier != plan.expert_tier
            or authorized.context.receiver_device_id != plan.peer_device_id
        ):
            raise PermissionError("remote execution route changed after Core admission")
        execution = create_remote_execution_request(
            self._peer_service.credentials,
            execution_id=_execution_id(plan.plan_id, record.revision),
            plan_id=plan.plan_id,
            context=authorized.context,
            capability=authorized.declaration,
            context_tokens=prepared.context_tokens,
            maximum_output_tokens=prepared.maximum_output_tokens,
            json_output=prepared.json_output,
            temperature=prepared.temperature,
        )
        trust = PairedPeerTrust(
            self._peer_service.credentials,
            tuple(item.approval for item in self._enrollments.active()),
            self._owner_id,
        )
        authenticated, raw = self._client_factory(trust).request(
            plan.peer_device_id, dumps_document(execution).encode("utf-8"),
        )
        result = loads_document(raw.decode("utf-8"))
        if not isinstance(result, RemoteExecutionResult):
            raise TypeError("remote execution returned an unexpected contract")
        if authenticated.device_id != plan.peer_device_id:
            raise PermissionError("remote execution TLS identity changed")
        identity = authorized.enrollment.approval.peer_identity
        local_fingerprint = self._peer_service.credentials.tls_certificate.fingerprint(
            hashes.SHA256(),
        ).hex()
        verify_remote_context_receipt(
            result.context_receipt, authorized.context, identity,
        )
        verify_remote_execution_result(
            result, execution, identity, local_fingerprint,
        )
        disclosure = self._context.record(authorized, result.context_receipt, (
            "privacy.approved", "capability.signed_and_current",
            "context.bytes_exact", "context.receipt_verified",
            "execution.request_signed", "execution.result_signed",
        ))
        if result.status is not RemoteExecutionStatus.COMPLETED:
            raise RuntimeError(result.failure_code or "remote.execution.failed")
        assert result.content is not None and result.metrics is not None
        response = InferenceResponse(result.content, result.metrics)
        return AuthenticatedRemoteInference(response, execution, result, disclosure)


def _execution_id(plan_id: str, revision: int) -> str:
    digest = hashlib.sha256(f"{plan_id}|{revision}".encode("utf-8")).hexdigest()
    return "remote-execution-" + digest[:32]


def _context_request_id(core_request_id: str) -> str:
    digest = hashlib.sha256(core_request_id.encode("utf-8")).hexdigest()
    return "remote-context-request-" + digest[:32]
