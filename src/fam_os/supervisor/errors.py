"""Stable supervisor boundary errors."""


class SupervisorError(RuntimeError):
    """Base error for deterministic supervisor operations."""


class ServiceLifecycleError(SupervisorError):
    """A service lifecycle operation could not be completed."""


class ResourceObservationError(SupervisorError):
    """Resource-controller data was present but invalid."""


class SupervisorAuthorizationError(SupervisorError):
    """Caller authority is missing or insufficient."""


class ServiceOwnershipError(SupervisorError):
    """A caller addressed a service it does not own."""


class ServiceDefinitionConflictError(SupervisorError):
    """An owned service ID was reused with different declared intent."""


class AuditEmissionError(SupervisorError):
    """A required immutable audit record could not be persisted."""


class AuditIntegrityError(AuditEmissionError):
    """An existing audit chain failed integrity verification."""


class ServiceRecoveryError(SupervisorError):
    """A service could not reach a verified safe inactive state."""
