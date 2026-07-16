"""Remote disconnect and partial-result recovery."""

from dataclasses import dataclass
from enum import StrEnum

FABRIC_RECOVERY_CONTRACT_VERSION = "fam.fabric.recovery/v1alpha1"


class RemoteFailureKind(StrEnum):
    DISCONNECTED = "disconnected"
    TIMEOUT = "timeout"
    PARTIAL_RESULT = "partial_result"
    VERIFICATION_FAILED = "verification_failed"


@dataclass(frozen=True, slots=True)
class FabricRecoveryDecision:
    failure: RemoteFailureKind
    discard_remote_output: bool
    retry_local: bool
    preserve_acceptance: bool
    reason_codes: tuple[str, ...]
    contract_version: str = FABRIC_RECOVERY_CONTRACT_VERSION


class FabricRecoveryPolicy:
    def decide(self, failure, local_candidate_available):
        return FabricRecoveryDecision(
            failure, True, local_candidate_available, True,
            (f"remote.{failure.value}",
             "fallback.local" if local_candidate_available else "fallback.unavailable"),
        )
