"""Authenticated permission-filtered MCP view of the Core ingress gateway."""

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from uuid import uuid4

from jsonschema import Draft202012Validator, ValidationError

from fam_os.adapters.mcp.ingress.auth import McpIngressAuthenticator
from fam_os.adapters.mcp.ingress.types import McpIngressOutcome, McpIngressTool
from fam_os.core.admission import RequestIdentity
from fam_os.core.contracts import ResultStatus
from fam_os.core.ingress import CoreIngressGateway, CoreIngressRequest


FAM_MCP_RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "request_id": {"type": "string"},
        "status": {"enum": ["completed", "verified", "withheld", "failed"]},
        "verified": {"type": "boolean"},
        "content": {"type": ["string", "null"]},
        "reason": {"type": "string"},
        "evidence_ids": {"type": "array", "items": {"type": "string"}},
        "failure_code": {"type": ["string", "null"]},
    },
    "required": [
        "request_id", "status", "verified", "content", "reason",
        "evidence_ids", "failure_code",
    ],
    "additionalProperties": False,
}
_AUTHENTICATED_SESSION = object()


@dataclass(frozen=True, slots=True)
class McpIngressLimits:
    max_visible_tools: int = 256
    max_request_bytes: int = 262_144
    max_result_bytes: int = 1_048_576

    def __post_init__(self) -> None:
        if min(self.max_visible_tools, self.max_request_bytes, self.max_result_bytes) <= 0:
            raise ValueError("MCP ingress limits must be positive")


class AuthenticatedMcpIngress:
    def __init__(
        self, identity: RequestIdentity, gateway: CoreIngressGateway,
        limits: McpIngressLimits = McpIngressLimits(),
        request_id_factory: Callable[[], str] = lambda: str(uuid4()),
        _authentication_proof=None,
    ):
        if _authentication_proof is not _AUTHENTICATED_SESSION:
            raise PermissionError("MCP ingress requires authenticated construction")
        self._identity = identity
        self._gateway = gateway
        self._limits = limits
        self._request_id_factory = request_id_factory

    @classmethod
    def authenticate(cls, token, authenticator: McpIngressAuthenticator, gateway, **kwargs):
        identity = authenticator.authenticate(token)
        return cls(
            identity, gateway, _authentication_proof=_AUTHENTICATED_SESSION, **kwargs
        )

    async def list_tools(self) -> tuple[McpIngressTool, ...]:
        capabilities = await self._gateway.visible_capabilities(self._identity)
        if len(capabilities) > self._limits.max_visible_tools:
            raise RuntimeError("MCP ingress visible capability limit exceeded")
        return tuple(_tool(item) for item in capabilities)

    async def call_tool(self, tool_name: str, arguments: dict) -> McpIngressOutcome:
        tools = await self.list_tools()
        tool = next((item for item in tools if item.name == tool_name), None)
        if tool is None:
            return _error("The requested FAM capability is unavailable.", "ingress.denied")
        if not isinstance(arguments, dict):
            return _error("The capability input is invalid.", "ingress.input_invalid")
        if not _within_limit(arguments, self._limits.max_request_bytes):
            return _error("The request is too large.", "ingress.request_too_large")
        try:
            Draft202012Validator(_mutable(tool.input_schema)).validate(arguments)
        except ValidationError:
            return _error("The capability input is invalid.", "ingress.input_invalid")
        request = CoreIngressRequest(
            self._request_id_factory(), tool.capability_id, arguments
        )
        try:
            result = await self._gateway.invoke(self._identity, request)
        except Exception:
            return _error("The request could not be completed.", "ingress.gateway_failure")
        payload = _result_payload(result)
        if not _within_limit(payload, self._limits.max_result_bytes):
            return _error("The result exceeded the safe size limit.", "ingress.result_too_large")
        is_error = result.status in {ResultStatus.FAILED, ResultStatus.WITHHELD}
        message = result.reason if is_error else "FAM request completed."
        return McpIngressOutcome(is_error, message, payload)


def _tool(capability):
    digest = hashlib.sha256(capability.capability_id.encode()).hexdigest()[:24]
    return McpIngressTool(
        f"fam_{digest}", capability.capability_id, capability.display_name,
        capability.description, capability.input_schema, FAM_MCP_RESULT_SCHEMA,
    )


def _result_payload(result):
    return {
        "request_id": result.request_id, "status": result.status.value,
        "verified": result.verified, "content": result.content,
        "reason": result.reason, "evidence_ids": list(result.evidence_ids),
        "failure_code": result.failure.code if result.failure is not None else None,
    }


def _error(message, code):
    payload = {
        "request_id": "unavailable", "status": "failed", "verified": False,
        "content": None, "reason": message, "evidence_ids": [],
        "failure_code": code,
    }
    return McpIngressOutcome(True, message, payload)


def _within_limit(value, limit):
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    except (TypeError, ValueError):
        return False
    return len(encoded) <= limit


def _mutable(value):
    if hasattr(value, "items"):
        return {key: _mutable(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_mutable(item) for item in value]
    return value
