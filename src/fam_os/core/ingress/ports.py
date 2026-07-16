"""Ports for permission-filtered client ingress through the Core lifecycle."""

from typing import Protocol

from fam_os.applications.payloads import JsonObject
from fam_os.core.admission import AdmittedTaskRequest, RequestIdentity
from fam_os.core.contracts import TaskResult
from fam_os.core.ingress.contracts import CoreIngressRequest, IngressCapability


class IngressCapabilityRegistry(Protocol):
    def entries(self) -> tuple[IngressCapability, ...]: ...

    def get(self, capability_id: str) -> IngressCapability | None: ...


class CoreTaskExecutor(Protocol):
    async def execute(
        self, admitted: AdmittedTaskRequest, parameters: JsonObject
    ) -> TaskResult: ...


class CoreIngressGateway(Protocol):
    async def visible_capabilities(
        self, identity: RequestIdentity
    ) -> tuple[IngressCapability, ...]: ...

    async def invoke(
        self, identity: RequestIdentity, request: CoreIngressRequest
    ) -> TaskResult: ...
