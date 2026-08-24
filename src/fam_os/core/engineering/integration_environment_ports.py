"""Replaceable execution boundary for integration environments."""

from pathlib import Path
from typing import Protocol

from fam_os.core.engineering.integration_environment import (
    IntegrationEnvironmentPlan,
    IntegrationExecutionPermit,
)
from fam_os.core.engineering.integration_environment_receipts import (
    IntegrationEnvironmentReceipt,
)
from fam_os.core.engineering.integration_network import (
    IntegrationNetworkEnforcementRequest,
    IntegrationNetworkLease,
    IntegrationNetworkUsage,
)


class IntegrationEnvironmentControl(Protocol):
    def cancelled(self) -> bool: ...

    def authorization_active(self) -> bool: ...


class IntegrationEnvironmentExecutor(Protocol):
    def launch(
        self,
        plan: IntegrationEnvironmentPlan,
        candidate_root: Path,
        permit: IntegrationExecutionPermit,
        control: IntegrationEnvironmentControl,
    ) -> IntegrationEnvironmentReceipt: ...

    def cleanup(
        self,
        plan: IntegrationEnvironmentPlan,
        receipt: IntegrationEnvironmentReceipt,
        candidate_root: Path,
        permit: IntegrationExecutionPermit,
    ) -> IntegrationEnvironmentReceipt: ...


class IntegrationNetworkEnforcementBroker(Protocol):
    def open(
        self, request: IntegrationNetworkEnforcementRequest,
    ) -> IntegrationNetworkLease: ...

    def observe(self, lease: IntegrationNetworkLease) -> IntegrationNetworkUsage: ...

    def close(self, lease: IntegrationNetworkLease) -> IntegrationNetworkUsage: ...

    def recover(
        self, request: IntegrationNetworkEnforcementRequest,
    ) -> IntegrationNetworkUsage: ...


class IntegrationNetworkAuthoritySigner(Protocol):
    @property
    def key_id(self) -> str: ...

    def sign(
        self, request: IntegrationNetworkEnforcementRequest,
    ) -> IntegrationNetworkEnforcementRequest: ...
