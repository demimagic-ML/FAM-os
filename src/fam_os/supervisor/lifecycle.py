"""Ownership-aware idempotent unprivileged service lifecycle use case."""

from __future__ import annotations

from dataclasses import dataclass

from fam_os.supervisor.access import SupervisorAuthorizer, SupervisorCallContext
from fam_os.supervisor.boundary import SupervisorCapability
from fam_os.supervisor.contracts import ServiceDefinition, ServiceState, ServiceStatus
from fam_os.supervisor.errors import ServiceLifecycleError
from fam_os.supervisor.ownership import OwnedService, ServiceOwnershipRegistry
from fam_os.supervisor.ports import ServiceLifecycle


@dataclass(slots=True)
class OwnedServiceLifecycle:
    lifecycle: ServiceLifecycle
    authorizer: SupervisorAuthorizer
    registry: ServiceOwnershipRegistry

    def start(
        self, context: SupervisorCallContext, definition: ServiceDefinition
    ) -> ServiceStatus:
        self.declare(context, definition)
        current = self.lifecycle.status(definition.service_id)
        if current.state in {ServiceState.ACTIVE, ServiceState.ACTIVATING}:
            return current
        if current.state is ServiceState.DEACTIVATING:
            raise ServiceLifecycleError("cannot start a deactivating owned service")
        return self.lifecycle.start(definition)

    def declare(
        self, context: SupervisorCallContext, definition: ServiceDefinition
    ) -> OwnedService:
        self._authorize(
            context,
            SupervisorCapability.START_UNPRIVILEGED_SERVICE,
            definition.service_id,
        )
        return self.registry.claim(
            OwnedService(context.principal_id, context.session_id, definition)
        )

    def stop(
        self, context: SupervisorCallContext, service_id: str
    ) -> ServiceStatus:
        self._authorize(context, SupervisorCapability.STOP_OWNED_SERVICE, service_id)
        self._require_owned(context, service_id)
        current = self.lifecycle.status(service_id)
        if current.state in {
            ServiceState.INACTIVE,
            ServiceState.UNKNOWN,
            ServiceState.DEACTIVATING,
        }:
            return current
        return self.lifecycle.stop(service_id)

    def status(
        self, context: SupervisorCallContext, service_id: str
    ) -> ServiceStatus:
        self._authorize(
            context, SupervisorCapability.READ_OWNED_SERVICE_STATUS, service_id
        )
        self._require_owned(context, service_id)
        return self.lifecycle.status(service_id)

    def _authorize(
        self,
        context: SupervisorCallContext,
        capability: SupervisorCapability,
        service_id: str,
    ) -> None:
        self.authorizer.require(context, capability, service_id)

    def _require_owned(
        self, context: SupervisorCallContext, service_id: str
    ) -> OwnedService:
        return self.registry.require_owned(
            service_id, context.principal_id, context.session_id
        )
