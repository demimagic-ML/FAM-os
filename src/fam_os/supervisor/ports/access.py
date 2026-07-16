"""Enforcement port for declared service access grants."""

from typing import Protocol

from fam_os.supervisor.access_contracts import (
    AccessApplicationEvidence,
    AccessResourceDescriptor,
    ServiceAccessGrant,
)


class ServiceAccessAdapter(Protocol):
    def grant(
        self, grant: ServiceAccessGrant, resource: AccessResourceDescriptor
    ) -> AccessApplicationEvidence: ...

    def revoke(
        self, grant: ServiceAccessGrant, resource: AccessResourceDescriptor
    ) -> AccessApplicationEvidence: ...
