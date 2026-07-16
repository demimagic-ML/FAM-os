"""Core request admission boundary."""

from fam_os.core.admission.contracts import (
    AdmittedTaskRequest,
    RequestAdmissionOutcome,
    RequestAuthorityGrant,
    RequestIdentity,
    RequestPermissionContext,
)
from fam_os.core.admission.ports import RequestAuthorityRegistry, RequestReplayRegistry
from fam_os.core.admission.registry import (
    InMemoryRequestAuthorityRegistry,
    InMemoryRequestReplayRegistry,
)
from fam_os.core.admission.service import RequestAdmissionService

__all__ = [
    "AdmittedTaskRequest",
    "InMemoryRequestAuthorityRegistry",
    "InMemoryRequestReplayRegistry",
    "RequestAdmissionOutcome",
    "RequestAdmissionService",
    "RequestAuthorityGrant",
    "RequestAuthorityRegistry",
    "RequestIdentity",
    "RequestPermissionContext",
    "RequestReplayRegistry",
]
