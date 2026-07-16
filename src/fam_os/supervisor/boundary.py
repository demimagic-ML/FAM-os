"""Declared capability and non-goal boundary for the FAM Supervisor."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


SUPERVISOR_BOUNDARY_CONTRACT_VERSION = "fam.supervisor.boundary/v1alpha1"


class SupervisorTrustScope(StrEnum):
    USER_SESSION = "user_session"


class SupervisorCapability(StrEnum):
    START_UNPRIVILEGED_SERVICE = "start_unprivileged_service"
    STOP_OWNED_SERVICE = "stop_owned_service"
    READ_OWNED_SERVICE_STATUS = "read_owned_service_status"
    APPLY_SERVICE_RESOURCE_LIMITS = "apply_service_resource_limits"
    OBSERVE_OWNED_SERVICE_RESOURCES = "observe_owned_service_resources"
    GRANT_DECLARED_DEVICE_ACCESS = "grant_declared_device_access"
    GRANT_DECLARED_FILESYSTEM_ACCESS = "grant_declared_filesystem_access"
    EMIT_IMMUTABLE_AUDIT_EVENT = "emit_immutable_audit_event"
    RECOVER_FAILED_SERVICE = "recover_failed_service"
    SAFE_TERMINATE_OWNED_SERVICE = "safe_terminate_owned_service"


class SupervisorNonGoal(StrEnum):
    MODEL_INFERENCE = "model_inference"
    PROMPT_INTERPRETATION = "prompt_interpretation"
    ROUTING_OR_PLANNING = "routing_or_planning"
    MEMORY_RETRIEVAL = "memory_retrieval"
    CONTENT_VERIFICATION = "content_verification"
    APPLICATION_DECISIONS = "application_decisions"
    ARBITRARY_PROCESS_CONTROL = "arbitrary_process_control"
    SYSTEM_SERVICE_ADMINISTRATION = "system_service_administration"
    CREDENTIAL_OR_SECRET_MANAGEMENT = "credential_or_secret_management"
    PACKAGE_OR_MODEL_INSTALLATION = "package_or_model_installation"


@dataclass(frozen=True, slots=True)
class SupervisorBoundary:
    boundary_id: str
    trust_scope: SupervisorTrustScope
    implemented_capabilities: tuple[SupervisorCapability, ...]
    planned_capabilities: tuple[SupervisorCapability, ...]
    non_goals: tuple[SupervisorNonGoal, ...]
    authenticated_caller_required: bool = True
    system_service_control_allowed: bool = False
    model_logic_allowed: bool = False
    contract_version: str = SUPERVISOR_BOUNDARY_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if not self.boundary_id.strip():
            raise ValueError("supervisor boundary_id must not be empty")
        if self.contract_version != SUPERVISOR_BOUNDARY_CONTRACT_VERSION:
            raise ValueError("unsupported supervisor-boundary contract_version")
        if not self.authenticated_caller_required:
            raise ValueError("supervisor requires an authenticated caller")
        if self.system_service_control_allowed or self.model_logic_allowed:
            raise ValueError("supervisor boundary cannot admit system control or model logic")
        _require_unique(
            self.implemented_capabilities, "implemented capabilities", True
        )
        _require_unique(self.planned_capabilities, "planned capabilities", False)
        _require_unique(self.non_goals, "non-goals", True)
        if set(self.implemented_capabilities) & set(self.planned_capabilities):
            raise ValueError("implemented and planned capabilities must be disjoint")

    def implements(self, capability: SupervisorCapability) -> bool:
        return capability in self.implemented_capabilities


def canonical_supervisor_boundary() -> SupervisorBoundary:
    implemented = (
        SupervisorCapability.START_UNPRIVILEGED_SERVICE,
        SupervisorCapability.STOP_OWNED_SERVICE,
        SupervisorCapability.READ_OWNED_SERVICE_STATUS,
        SupervisorCapability.APPLY_SERVICE_RESOURCE_LIMITS,
        SupervisorCapability.OBSERVE_OWNED_SERVICE_RESOURCES,
        SupervisorCapability.GRANT_DECLARED_DEVICE_ACCESS,
        SupervisorCapability.GRANT_DECLARED_FILESYSTEM_ACCESS,
        SupervisorCapability.EMIT_IMMUTABLE_AUDIT_EVENT,
        SupervisorCapability.RECOVER_FAILED_SERVICE,
        SupervisorCapability.SAFE_TERMINATE_OWNED_SERVICE,
    )
    planned = ()
    return SupervisorBoundary(
        "fam-supervisor.v1",
        SupervisorTrustScope.USER_SESSION,
        implemented,
        planned,
        tuple(SupervisorNonGoal),
    )


def _require_unique(
    values: tuple[object, ...], name: str, require_non_empty: bool
) -> None:
    if (require_non_empty and not values) or len(set(values)) != len(values):
        raise ValueError(f"supervisor {name} must be unique and valid")
