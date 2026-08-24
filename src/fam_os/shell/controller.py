"""Thin Shell controller; all task and authority policy stays in Core."""

import hashlib
import os
from collections.abc import Callable
from uuid import uuid4

from fam_os.memory import (
    DocumentCorrectionRequest,
    DocumentDeletionRequest,
    DocumentExpirationRequest,
)
from fam_os.adaptation import AdaptationControlOperation, LiveAdaptationControlRequest
from fam_os.fabric import (
    PeerManagementOperation,
    PeerManagementRequest,
    RemoteContextSendRequest,
    RemoteExecutionAuthority,
    RemoteTaskDescriptor,
)
from fam_os.product.owner_identity import local_owner_id
from fam_os.shell.contracts import (
    ShellAskCommand,
    ShellCancelCommand,
    ShellContext,
    ShellDecision,
    ShellDecisionCommand,
    ShellRunState,
    ShellSessionSnapshot,
)
from fam_os.shell.state import accept_snapshot
from fam_os.shell.memory_contracts import (
    ShellMemoryOperation,
    ShellMemoryQuery,
    ShellMemoryResponse,
)
from fam_os.shell.adaptation_contracts import (
    ShellAdaptationOperation,
    ShellAdaptationQuery,
    ShellAdaptationResponse,
)
from fam_os.shell.peer_contracts import (
    ShellPeerOperation, ShellPeerProbeRequest, ShellPeerQuery, ShellPeerResponse,
)


def _identifier() -> str:
    return str(uuid4())


class ShellController:
    def __init__(
        self, client, request_id_factory: Callable[[], str] = _identifier,
        memory_session_id: str | None = None,
        owner_id: str | None = None,
    ):
        self._client = client
        self._request_id_factory = request_id_factory
        self._memory_session_id = memory_session_id or f"shell-memory-{_identifier()}"
        self._owner_id = owner_id or local_owner_id(os.geteuid())
        self._contexts: dict[str, ShellContext] = {}
        self._snapshot: ShellSessionSnapshot | None = None

    @property
    def snapshot(self):
        return self._snapshot

    @property
    def owner_id(self) -> str:
        return self._owner_id

    def contexts(self):
        return tuple(self._contexts.values())

    def add_context(self, context: ShellContext) -> None:
        self._require_context_mutable()
        if context.context_id in self._contexts:
            raise ValueError("shell context already exists")
        self._contexts[context.context_id] = context

    def remove_context(self, context_id: str) -> None:
        self._require_context_mutable()
        if self._contexts.pop(context_id, None) is None:
            raise KeyError("shell context does not exist")

    def ask(self, prompt: str, verification_required=False):
        return self._ask(prompt, verification_required, None)

    def ask_remote(
        self, prompt: str, authority: RemoteExecutionAuthority,
        verification_required: bool = False,
    ):
        if self.contexts():
            raise PermissionError(
                "remote inference cannot inherit application context authority",
            )
        return self._ask(prompt, verification_required, authority)

    def _ask(self, prompt, verification_required, remote_authority):
        if self._snapshot is not None and self._snapshot.state is not ShellRunState.TERMINAL:
            raise RuntimeError("a shell request is already active")
        capabilities = tuple(dict.fromkeys(
            capability
            for context in self.contexts()
            for capability in context.capability_ids
        ))
        command = ShellAskCommand(
            self._request_id_factory(), prompt, self.contexts(), capabilities,
            verification_required, memory_session_id=self._memory_session_id,
            remote_authority=remote_authority,
        )
        incoming = self._client.ask(command)
        if incoming.request_id != command.request_id:
            raise ValueError("Core returned the wrong shell request")
        self._snapshot = accept_snapshot(None, incoming)
        return self._snapshot

    def refresh(self):
        current = self._require_snapshot()
        incoming = self._client.snapshot(current.session_id)
        self._snapshot = accept_snapshot(current, incoming)
        return self._snapshot

    def decide(self, decision: ShellDecision):
        current = self._require_snapshot()
        if current.approval is None:
            raise RuntimeError("shell request is not waiting for approval")
        command = ShellDecisionCommand(
            current.session_id, current.revision,
            current.approval.approval_id, decision,
        )
        self._snapshot = accept_snapshot(current, self._client.decide(command))
        return self._snapshot

    def cancel(self):
        current = self._require_snapshot()
        command = ShellCancelCommand(current.session_id, current.revision)
        self._snapshot = accept_snapshot(current, self._client.cancel(command))
        return self._snapshot

    def memory_list(self, offset=0, limit=100):
        query = ShellMemoryQuery(
            self._request_id_factory(), ShellMemoryOperation.LIST,
            offset=offset, limit=limit,
        )
        return self._accept_memory(query, self._client.memory_query(query))

    def memory_inspect(self, document_id):
        query = ShellMemoryQuery(
            self._request_id_factory(), ShellMemoryOperation.INSPECT,
            document_id, limit=1,
        )
        return self._accept_memory(query, self._client.memory_query(query))

    def memory_export(self, document_id):
        query = ShellMemoryQuery(
            self._request_id_factory(), ShellMemoryOperation.EXPORT,
            document_id, limit=1,
        )
        return self._accept_memory(query, self._client.memory_query(query))

    def memory_receipts(self, offset=0, limit=100):
        query = ShellMemoryQuery(
            self._request_id_factory(), ShellMemoryOperation.RECEIPTS,
            offset=offset, limit=limit,
        )
        return self._accept_memory(query, self._client.memory_query(query))

    def memory_correct(self, document_id, expected_digest, content, confirmed):
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        request = DocumentCorrectionRequest(
            self._request_id_factory(), document_id, expected_digest,
            content, digest, confirmed,
        )
        return self._accept_memory(request, self._client.memory_correct(request))

    def memory_expire(self, grant_id, confirmed):
        request = DocumentExpirationRequest(
            self._request_id_factory(), grant_id, confirmed,
        )
        return self._accept_memory(request, self._client.memory_expire(request))

    def memory_delete(self, document_id, expected_digest, confirmed):
        request = DocumentDeletionRequest(
            self._request_id_factory(), document_id, expected_digest, confirmed,
        )
        return self._accept_memory(request, self._client.memory_delete(request))

    def adaptation_query(self, operation, offset=0, limit=100):
        selected_operation = ShellAdaptationOperation(operation)
        query = ShellAdaptationQuery(
            self._request_id_factory(), selected_operation,
            offset, 1 if selected_operation is ShellAdaptationOperation.STATUS else limit,
        )
        return self._accept_adaptation(query, self._client.adaptation_query(query))

    def adaptation_control(self, operation, confirmed, workflow_id=None):
        request = LiveAdaptationControlRequest(
            self._request_id_factory(), AdaptationControlOperation(operation),
            confirmed, workflow_id,
        )
        return self._accept_adaptation(
            request, self._client.adaptation_control(request),
        )

    def peer_query(self, operation, offset=0, limit=100):
        query = ShellPeerQuery(
            self._request_id_factory(), ShellPeerOperation(operation), offset, limit,
        )
        return self._accept_peer(query, self._client.peer_query(query))

    def peer_probe(self, enrollment_id):
        request = ShellPeerProbeRequest(self._request_id_factory(), enrollment_id)
        return self._accept_peer(request, self._client.peer_probe(request))

    def peer_control(
        self, operation, enrollment_id, expected_revision, confirmed,
        reason_code, privacy_policy=None,
    ):
        request = PeerManagementRequest(
            self._request_id_factory(), self._owner_id,
            PeerManagementOperation(operation), enrollment_id,
            expected_revision, confirmed, reason_code, privacy_policy,
        )
        return self._accept_peer(request, self._client.peer_control(request))

    def peer_context(
        self, enrollment_id, target_expert_id, capability_declaration_id,
        expected_privacy_revision, purpose_id, workspace_id, sensitivity,
        intent_id, capability_ids, assurance_id, maximum_output_bytes,
    ):
        request = RemoteContextSendRequest(
            "peer-context-" + self._request_id_factory(),
            enrollment_id, target_expert_id,
            capability_declaration_id, expected_privacy_revision,
            purpose_id, workspace_id, sensitivity,
            RemoteTaskDescriptor(
                intent_id, capability_ids, assurance_id, maximum_output_bytes,
            ),
        )
        return self._accept_peer(request, self._client.peer_context(request))

    @staticmethod
    def _accept_memory(request, response):
        if not isinstance(response, ShellMemoryResponse):
            raise ValueError("Core returned an invalid Shell memory response")
        if response.request_id != request.request_id:
            raise ValueError("Core returned the wrong Shell memory request")
        expected = request.operation if isinstance(request, ShellMemoryQuery) else {
            DocumentCorrectionRequest: ShellMemoryOperation.CORRECT,
            DocumentExpirationRequest: ShellMemoryOperation.EXPIRE,
            DocumentDeletionRequest: ShellMemoryOperation.DELETE,
        }.get(type(request))
        if response.operation is not expected:
            raise ValueError("Core returned the wrong Shell memory operation")
        return response

    @staticmethod
    def _accept_adaptation(request, response):
        if not isinstance(response, ShellAdaptationResponse):
            raise ValueError("Core returned an invalid Shell adaptation response")
        if response.request_id != request.request_id:
            raise ValueError("Core returned the wrong Shell adaptation request")
        if isinstance(request, ShellAdaptationQuery):
            expected = request.operation
        else:
            expected = ShellAdaptationOperation.RECEIPTS
        if response.operation is not expected:
            raise ValueError("Core returned the wrong Shell adaptation operation")
        return response

    @staticmethod
    def _accept_peer(request, response):
        if not isinstance(response, ShellPeerResponse) or response.request_id != request.request_id:
            raise ValueError("Core returned an invalid Shell peer response")
        expected = (
            request.operation if isinstance(request, ShellPeerQuery)
            else ShellPeerOperation.PROBE if isinstance(request, ShellPeerProbeRequest)
            else ShellPeerOperation.CONTEXT if isinstance(request, RemoteContextSendRequest)
            else ShellPeerOperation.RECEIPTS
        )
        if response.operation is not expected:
            raise ValueError("Core returned the wrong Shell peer operation")
        return response

    def _require_snapshot(self):
        if self._snapshot is None:
            raise RuntimeError("shell has no active request")
        return self._snapshot

    def _require_context_mutable(self):
        if self._snapshot is not None and self._snapshot.state is not ShellRunState.TERMINAL:
            raise RuntimeError("context is frozen while a shell request is active")
