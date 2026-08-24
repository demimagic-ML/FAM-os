"""Production Application Fabric policy and discovery services."""

import os
from dataclasses import dataclass
from pathlib import Path

from fam_os.adapters.audit import ApplicationJsonlAuditSink
from fam_os.adapters.linux.application_discovery import (
    LinuxApplicationDiscovery,
    LinuxApplicationDiscoverySettings,
)
from fam_os.core.lifecycle import (
    ApplicationActionExecutionService,
    ApplicationStepService,
    ConfirmationTransitionService,
    PlanLifecycleService,
)
from fam_os.product.composition.application_conditions import (
    LiveApplicationConditionVerifier,
)
from fam_os.product.composition.fallbacks import ProductFallbacks
from fam_os.product.composition.live_application_provider import LiveApplicationProvider
from fam_os.product.composition.mcp_clients import ProductMcpClients
from fam_os.product.composition.os_tools import ProductOsTools
from fam_os.product.composition.owner_filesystem import OwnerFilesystem


@dataclass(frozen=True, slots=True)
class ApplicationServices:
    provider: LiveApplicationProvider
    steps: ApplicationStepService
    actions: ApplicationActionExecutionService
    confirmations: ConfirmationTransitionService
    discovery: object
    mcp_clients: ProductMcpClients
    os_tools: ProductOsTools
    owner_filesystem: OwnerFilesystem
    fallbacks: ProductFallbacks
    verifier: LiveApplicationConditionVerifier
    audit: ApplicationJsonlAuditSink

    @classmethod
    def compose(cls, fabric, repositories, state_root: Path) -> "ApplicationServices":
        mcp_clients = ProductMcpClients.from_file(
            fabric.registry, state_root / "config/mcp-clients.json",
        )
        os_tools = ProductOsTools.from_file(
            fabric.registry, state_root / "config/os-tools.json",
        )
        owner_filesystem = OwnerFilesystem(fabric.registry, Path.home())
        fallbacks = ProductFallbacks.from_file(
            fabric.registry, state_root / "config/fallbacks.json",
        )
        mcp_clients.start()
        try:
            owner_filesystem.start()
            os_tools.start()
            fallbacks.start()
        except BaseException:
            fallbacks.close()
            os_tools.close()
            owner_filesystem.close()
            mcp_clients.close()
            raise
        provider = LiveApplicationProvider(
            fabric.registry, fabric.broker,
            (mcp_clients, os_tools, owner_filesystem, fallbacks),
        )
        lifecycle = PlanLifecycleService(repositories.plans)
        audit_root = state_root / "audit"
        audit_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(audit_root, 0o700)
        verifier = LiveApplicationConditionVerifier(provider)
        audit = ApplicationJsonlAuditSink(
            (audit_root / "application-actions.jsonl").absolute(),
        )
        discovery = _discovery().collect()
        return cls(
            provider,
            ApplicationStepService(
                lifecycle, provider, repositories.application_permissions,
            ),
            ApplicationActionExecutionService(
                lifecycle, provider, repositories.application_permissions,
                verifier, audit, repositories.action_execution_replay,
                repositories.actions,
            ),
            ConfirmationTransitionService(
                lifecycle, repositories.application_permissions,
                repositories.confirmation_replay, repositories.actions,
            ),
            discovery,
            mcp_clients,
            os_tools,
            owner_filesystem,
            fallbacks,
            verifier,
            audit,
        )

    def close(self) -> None:
        self.fallbacks.close()
        self.os_tools.close()
        self.owner_filesystem.close()
        self.mcp_clients.close()


def _discovery() -> LinuxApplicationDiscovery:
    home = Path.home()
    directories = tuple(
        path for path in (
            home / ".local/share/applications",
            Path("/usr/local/share/applications"),
            Path("/usr/share/applications"),
        )
        if path.is_dir()
    )
    session_type = os.environ.get("XDG_SESSION_TYPE", "unknown")
    return LinuxApplicationDiscovery.standard(LinuxApplicationDiscoverySettings(
        directories, session_type, bool(os.environ.get("DISPLAY")), False,
    ))
