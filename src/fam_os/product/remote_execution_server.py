"""In-memory remote expert execution behind the authenticated peer listener."""

from __future__ import annotations

from datetime import UTC, datetime

from fam_os.core.ports.inference import InferenceRequest
from fam_os.core.production.contracts import ModelIntent
from fam_os.core.production.generation_input import PreparedGenerationInput
from fam_os.fabric import (
    RemoteExecutionStatus,
    RemoteRawContextKind,
    create_remote_execution_result,
    verify_capability_declaration,
)


class ProductRemoteExecutionServer:
    def __init__(
        self, runtime, capability_source, model_loader=None, *, clock=None,
    ) -> None:
        self._runtime = runtime
        self._capability_source = capability_source
        self._loader = model_loader
        self._clock = clock or (lambda: datetime.now(UTC))

    def execute(self, credentials, peer, request, receipt, observed_at):
        self._validate_capability(credentials, request, observed_at)
        prepared, intent = self._prepare(request)
        started_at = self._clock()
        try:
            if self._loader is not None:
                self._loader.ensure_model(request.capability.model_ref)
            response = self._runtime.chat(InferenceRequest(
                request.capability.model_ref, prepared.messages(intent),
                request.context_tokens, request.maximum_output_tokens,
                json_output=request.json_output, temperature=request.temperature,
            ))
            content = response.content
            if (
                not content
                or response.metrics.model_ref != request.capability.model_ref
                or len(content.encode("utf-8"))
                > request.context.descriptor.maximum_output_bytes
            ):
                raise RuntimeError("remote provider returned an invalid bounded result")
        except Exception:
            return create_remote_execution_result(
                credentials, request, receipt, peer.certificate_sha256,
                status=RemoteExecutionStatus.FAILED, content=None,
                failure_code="remote.runtime.failed", metrics=None,
                started_at=started_at, completed_at=self._clock(),
            )
        return create_remote_execution_result(
            credentials, request, receipt, peer.certificate_sha256,
            status=RemoteExecutionStatus.COMPLETED, content=content,
            failure_code=None, metrics=response.metrics,
            started_at=started_at, completed_at=self._clock(),
        )

    def _validate_capability(self, credentials, request, observed_at) -> None:
        declaration = request.capability
        verify_capability_declaration(
            declaration, credentials.identity, observed_at,
        )
        required = set(request.context.descriptor.capability_ids)
        current = tuple(self._capability_source(credentials, observed_at))
        if not any(
            item.expert_id == declaration.expert_id
            and item.model_ref == declaration.model_ref
            and item.expert_tier == declaration.expert_tier
            and item.manifest_sha256 == declaration.manifest_sha256
            and required.issubset(item.capability_ids)
            and request.context.content_bytes <= item.maximum_context_bytes
            and request.context_tokens * 4 <= item.maximum_context_bytes
            for item in current
        ):
            raise PermissionError(
                "remote execution capability is not currently installed and enabled",
            )

    @staticmethod
    def _prepare(request):
        try:
            intent = ModelIntent(request.context.descriptor.intent_id)
        except ValueError as error:
            raise ValueError("remote execution intent is unsupported") from error
        prompts = tuple(
            item.content for item in request.context.raw_fragments
            if item.kind is RemoteRawContextKind.PROMPT
        )
        if len(prompts) != 1:
            raise ValueError("remote execution requires exactly one prompt fragment")
        memory = "\n\n".join(
            item.content for item in request.context.raw_fragments
            if item.kind is RemoteRawContextKind.MEMORY
        )
        observations = "\n\n".join(
            item.content for item in request.context.raw_fragments
            if item.kind in {
                RemoteRawContextKind.FILE_EXCERPT,
                RemoteRawContextKind.RETRIEVAL,
            }
        )
        return PreparedGenerationInput(
            prompts[0], memory, observations, (), request.context_tokens,
            request.maximum_output_tokens, request.json_output,
            request.temperature,
        ), intent
