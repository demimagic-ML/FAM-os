"""Fail-closed authority policy for product recovery mode."""

from dataclasses import dataclass
from enum import StrEnum


RECOVERY_CONTRACT_VERSION = "fam.product.recovery/v1alpha1"


class RecoveryOperation(StrEnum):
    DIAGNOSE = "diagnose"
    EXPORT_AUDIT = "export_audit"
    EXPORT_MEMORY = "export_memory"
    ROLLBACK_RELEASE = "rollback_release"
    REPAIR_STATE = "repair_state"
    RUN_INFERENCE = "run_inference"
    APPLICATION_ACTION = "application_action"
    MUTATE_MEMORY = "mutate_memory"
    TRAIN_EXPERT = "train_expert"
    NETWORK_ACCESS = "network_access"


_ALLOWED = frozenset({
    RecoveryOperation.DIAGNOSE,
    RecoveryOperation.EXPORT_AUDIT,
    RecoveryOperation.EXPORT_MEMORY,
    RecoveryOperation.ROLLBACK_RELEASE,
    RecoveryOperation.REPAIR_STATE,
})


@dataclass(frozen=True, slots=True)
class RecoveryDecision:
    operation: RecoveryOperation
    allowed: bool
    network_allowed: bool
    reason: str
    contract_version: str = RECOVERY_CONTRACT_VERSION


class RecoveryModePolicy:
    def decide(self, operation: RecoveryOperation) -> RecoveryDecision:
        allowed = operation in _ALLOWED
        return RecoveryDecision(
            operation, allowed, False,
            "bounded_recovery_operation" if allowed else "recovery_mode_denies_side_effect",
        )
