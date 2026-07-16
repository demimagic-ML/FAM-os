"""Remote expert capability and deny-by-default context privacy policy."""

from dataclasses import dataclass
from enum import StrEnum

REMOTE_PRIVACY_CONTRACT_VERSION = "fam.fabric.remote-privacy/v1alpha1"


class RemoteContextSensitivity(StrEnum):
    PUBLIC = "public"
    PRIVATE = "private"
    RESTRICTED = "restricted"


@dataclass(frozen=True, slots=True)
class RemoteExpertCapability:
    device_id: str
    expert_id: str
    capability_ids: tuple[str, ...]
    maximum_context_bytes: int
    verified_package_sha256: str


@dataclass(frozen=True, slots=True)
class RemotePrivacyPolicy:
    owner_id: str
    allowed_device_ids: tuple[str, ...]
    allowed_purpose_ids: tuple[str, ...]
    allowed_workspace_ids: tuple[str, ...]
    maximum_context_bytes: int
    allowed_sensitivities: tuple[RemoteContextSensitivity, ...]
    raw_content_allowed: bool = False


@dataclass(frozen=True, slots=True)
class RemoteContextRequest:
    owner_id: str
    device_id: str
    purpose_id: str
    workspace_id: str
    sensitivity: RemoteContextSensitivity
    context_bytes: int
    contains_raw_content: bool


@dataclass(frozen=True, slots=True)
class RemotePrivacyDecision:
    allowed: bool
    reason_codes: tuple[str, ...]
    contract_version: str = REMOTE_PRIVACY_CONTRACT_VERSION


class RemotePrivacyEvaluator:
    def decide(self, policy, request):
        reasons = []
        checks = (
            (request.owner_id == policy.owner_id, "privacy.owner"),
            (request.device_id in policy.allowed_device_ids, "privacy.device"),
            (request.purpose_id in policy.allowed_purpose_ids, "privacy.purpose"),
            (request.workspace_id in policy.allowed_workspace_ids, "privacy.workspace"),
            (request.sensitivity in policy.allowed_sensitivities, "privacy.sensitivity"),
            (request.context_bytes <= policy.maximum_context_bytes, "privacy.context-bytes"),
            (not request.contains_raw_content or policy.raw_content_allowed, "privacy.raw-content"),
        )
        reasons.extend(reason for passed, reason in checks if not passed)
        return RemotePrivacyDecision(not reasons, tuple(reasons))
