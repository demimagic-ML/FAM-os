"""Permission-filtered client ingress through Core admission."""

from fam_os.core.ingress.contracts import CoreIngressRequest, IngressCapability
from fam_os.core.ingress.ports import (
    CoreIngressGateway, CoreTaskExecutor, IngressCapabilityRegistry,
)
from fam_os.core.ingress.registry import InMemoryIngressCapabilityRegistry
from fam_os.core.ingress.service import LifecycleCoreIngressGateway
from fam_os.core.ingress.shell_views import (
    accepted_shell_snapshot, project_shell_snapshot,
)

__all__ = [
    "CoreIngressGateway", "CoreIngressRequest", "CoreTaskExecutor",
    "IngressCapability", "IngressCapabilityRegistry",
    "InMemoryIngressCapabilityRegistry", "LifecycleCoreIngressGateway",
    "accepted_shell_snapshot", "project_shell_snapshot",
]
