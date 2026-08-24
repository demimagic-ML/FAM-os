"""Synchronous Application Fabric facade over one supervised MCP worker."""

from datetime import datetime, timezone
from uuid import uuid4

from fam_os.adapters.mcp.types import mutable_json
from fam_os.applications import (
    ActionProposal, ActionResult, ActionStatus, ApplicationFailure,
    ApplicationFailureCategory, ApplicationRetryDisposition, ConditionEvidence,
    ConditionRequirement, ObservationResult, ObservationStatus, Reversibility,
)


class McpApplicationTransport:
    def __init__(self, worker, mapped, policy=None) -> None:
        self._worker = worker
        self._mapped = mapped
        self._policy = policy

    @property
    def connector_id(self) -> str:
        return self._mapped.registration.connector_id

    def observe(self, request):
        outcome = self._worker.observe(
            request.capability_id, mutable_json(request.parameters),
        )
        if outcome.succeeded:
            return ObservationResult(
                request.request_id, ObservationStatus.OBSERVED, _now(),
                outcome.payload, request.resource_uri,
            )
        return ObservationResult(
            request.request_id, ObservationStatus.FAILED, _now(),
            error=_failure(outcome.error_code or "mcp.provider_failure"),
        )

    def observation_parameters(
        self, capability_id: str, prompt: str, resource_uri: str | None,
    ) -> dict[str, object]:
        binding = self._mapped.binding(capability_id)
        if binding.primitive_kind.value == "resource" or self._policy is None:
            return {}
        tool_policy = self._policy.tool_policy(binding.primitive_name)
        if tool_policy is None:
            raise PermissionError("MCP observation tool is not owner approved")
        return tool_policy.observation_arguments(prompt, resource_uri)

    def prepare_action(self, request):
        binding = self._mapped.binding(request.capability_id)
        descriptor = binding.entry.capability
        reversal = None
        if descriptor.reversibility in {
            Reversibility.REVERSIBLE, Reversibility.COMPENSATABLE,
        }:
            raise PermissionError(
                "recoverable MCP actions require an explicit reversal capability"
            )
        postconditions = tuple(
            ConditionRequirement(item, item, f"Independently verify {item}.")
            for item in descriptor.postcondition_ids
        )
        return ActionProposal(
            f"mcp-proposal-{uuid4()}", request,
            {"provider": "mcp", "arguments": mutable_json(request.parameters)},
            descriptor.reversibility, descriptor.confirmation, postconditions,
            reversal_capability_id=reversal,
        )

    def execute_action(self, proposal, confirmation):
        outcome = self._worker.execute(
            proposal.request.capability_id,
            mutable_json(proposal.request.parameters),
        )
        if not outcome.succeeded:
            return ActionResult(
                proposal.proposal_id, ActionStatus.EXECUTION_FAILED, _now(),
                error=_failure(outcome.error_code or "mcp.provider_failure"),
            )
        evidence = tuple(
            ConditionEvidence(
                item.condition_id, item.verifier_id, True,
                "MCP provider asserted success; Core verification is still required.",
            )
            for item in proposal.postconditions
        )
        return ActionResult(
            proposal.proposal_id, ActionStatus.VERIFIED, _now(), evidence,
            outcome.payload, proposal.request.expected_revision,
            _revision(outcome.payload, proposal.request.expected_revision),
        )

    def close(self) -> None:
        self._worker.stop()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _revision(payload, fallback):
    value = payload.get("revision")
    return value if isinstance(value, str) and value.strip() else fallback


def _failure(code: str) -> ApplicationFailure:
    return ApplicationFailure(
        ApplicationFailureCategory.EXECUTION_FAILED, code,
        "The approved MCP provider operation did not complete.",
        ApplicationRetryDisposition.AFTER_STATE_CHANGE,
    )
