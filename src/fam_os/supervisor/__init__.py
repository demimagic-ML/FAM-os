"""Deterministic service and resource-control contracts."""

from fam_os.supervisor.boundary import (
    SUPERVISOR_BOUNDARY_CONTRACT_VERSION,
    SupervisorBoundary,
    SupervisorCapability,
    SupervisorNonGoal,
    SupervisorTrustScope,
    canonical_supervisor_boundary,
)
from fam_os.supervisor.access import SupervisorAuthorizer, SupervisorCallContext
from fam_os.supervisor.access_contracts import (
    AccessApplicationEvidence,
    AccessEvidenceStatus,
    AccessMode,
    AccessResourceDescriptor,
    AccessResourceKind,
    ServiceAccessGrant,
)
from fam_os.supervisor.access_control import ServiceAccessController
from fam_os.supervisor.audit import SupervisorAuditEmitter
from fam_os.supervisor.audit_contracts import (
    AUDIT_CONTRACT_VERSION,
    GENESIS_AUDIT_DIGEST,
    AuditChainVerification,
    SupervisorAuditIntent,
    SupervisorAuditOperation,
    SupervisorAuditOutcome,
    SupervisorAuditRecord,
)
from fam_os.supervisor.audited_access import AuditedServiceAccessController
from fam_os.supervisor.audited_constrained import AuditedConstrainedServiceLifecycle
from fam_os.supervisor.audited_lifecycle import AuditedOwnedServiceLifecycle
from fam_os.supervisor.access_registry import (
    InMemoryAccessGrantRegistry,
    InMemoryAccessResourceCatalog,
    RecordedAccessGrant,
)
from fam_os.supervisor.lifecycle import OwnedServiceLifecycle
from fam_os.supervisor.recovery import ServiceRecoveryController
from fam_os.supervisor.recovery_contracts import (
    ServiceTerminationDisposition,
    ServiceTerminationReason,
    ServiceTerminationReport,
)
from fam_os.supervisor.constrained import (
    ConstrainedServiceLifecycle,
    ConstrainedStartOutcome,
)
from fam_os.supervisor.limit_verification import (
    AppliedLimitCheck,
    AppliedLimitsVerification,
    LimitVerificationStatus,
    verify_applied_limits,
)
from fam_os.supervisor.ownership import (
    InMemoryServiceOwnershipRegistry,
    OwnedService,
    ServiceOwnershipRegistry,
)

from fam_os.supervisor.contracts import (
    BlockIoBandwidthCeiling,
    BlockIoBandwidthLimit,
    CountCeiling,
    CpuQuotaCeiling,
    PressureSample,
    PressureScope,
    ResourceCeiling,
    ResourceEvent,
    ResourceLimits,
    ResourceSnapshot,
    ServiceDefinition,
    ServiceState,
    ServiceStatus,
)
from fam_os.supervisor.errors import (
    AuditEmissionError,
    AuditIntegrityError,
    ResourceObservationError,
    ServiceDefinitionConflictError,
    ServiceLifecycleError,
    ServiceOwnershipError,
    ServiceRecoveryError,
    SupervisorAuthorizationError,
    SupervisorError,
)
from fam_os.supervisor.ports import (
    ResourceObserver,
    ServiceFailureReset,
    ServiceAccessAdapter,
    ServiceDefinitionProjector,
    ServiceLifecycle,
    SupervisorAuditSink,
)

__all__ = [
    "AUDIT_CONTRACT_VERSION",
    "GENESIS_AUDIT_DIGEST",
    "AuditChainVerification",
    "AuditEmissionError",
    "AuditIntegrityError",
    "AuditedOwnedServiceLifecycle",
    "AuditedConstrainedServiceLifecycle",
    "AuditedServiceAccessController",
    "SUPERVISOR_BOUNDARY_CONTRACT_VERSION",
    "CountCeiling",
    "BlockIoBandwidthCeiling",
    "BlockIoBandwidthLimit",
    "AccessApplicationEvidence",
    "AccessEvidenceStatus",
    "AccessMode",
    "AccessResourceDescriptor",
    "AccessResourceKind",
    "ConstrainedServiceLifecycle",
    "ConstrainedStartOutcome",
    "CpuQuotaCeiling",
    "AppliedLimitCheck",
    "AppliedLimitsVerification",
    "LimitVerificationStatus",
    "PressureSample",
    "PressureScope",
    "ResourceCeiling",
    "ResourceEvent",
    "ResourceLimits",
    "ResourceObservationError",
    "ResourceObserver",
    "ServiceFailureReset",
    "ResourceSnapshot",
    "ServiceDefinition",
    "ServiceDefinitionConflictError",
    "ServiceLifecycle",
    "ServiceLifecycleError",
    "ServiceOwnershipError",
    "ServiceRecoveryController",
    "ServiceRecoveryError",
    "ServiceState",
    "ServiceStatus",
    "ServiceTerminationDisposition",
    "ServiceTerminationReason",
    "ServiceTerminationReport",
    "SupervisorError",
    "SupervisorAuthorizationError",
    "SupervisorAuthorizer",
    "SupervisorAuditEmitter",
    "SupervisorAuditIntent",
    "SupervisorAuditOperation",
    "SupervisorAuditOutcome",
    "SupervisorAuditRecord",
    "SupervisorAuditSink",
    "SupervisorBoundary",
    "SupervisorCallContext",
    "SupervisorCapability",
    "SupervisorNonGoal",
    "SupervisorTrustScope",
    "canonical_supervisor_boundary",
    "InMemoryServiceOwnershipRegistry",
    "InMemoryAccessGrantRegistry",
    "InMemoryAccessResourceCatalog",
    "OwnedService",
    "OwnedServiceLifecycle",
    "RecordedAccessGrant",
    "ServiceAccessAdapter",
    "ServiceAccessController",
    "ServiceAccessGrant",
    "ServiceDefinitionProjector",
    "ServiceOwnershipRegistry",
    "verify_applied_limits",
]
