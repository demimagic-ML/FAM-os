"""Core orchestration that delegates privileged effects to an external broker."""

from datetime import datetime

from fam_os.core.engineering.grants import EngineeringAuthorityGrant
from fam_os.core.engineering.privileged import (
    HostAdministrationChangeSet, HostAdministrationReceipt, HostChangeStatus,
)
from fam_os.core.engineering.privileged_policy import (
    HostAdministrationBroker, HostAdministrationGate,
)


class EngineeringHostAdministrationService:
    def __init__(
        self,
        gate: HostAdministrationGate,
        broker: HostAdministrationBroker,
    ) -> None:
        self._gate = gate
        self._broker = broker

    def apply(
        self,
        change_set: HostAdministrationChangeSet,
        grant: EngineeringAuthorityGrant,
        authentication_context_id: str,
        *,
        instant: datetime,
    ) -> HostAdministrationReceipt:
        self._gate.authorize(
            change_set, grant, authentication_context_id, instant=instant,
        )
        receipt = self._broker.apply(change_set, authentication_context_id)
        if receipt.change_set_id != change_set.change_set_id:
            raise ValueError("host broker receipt changeset is mismatched")
        if receipt.owner_authentication_context_id != authentication_context_id:
            raise ValueError("host broker receipt authentication is mismatched")
        if not set(change_set.before_evidence_ids).issubset(receipt.before_evidence_ids):
            raise ValueError("host broker receipt omits required before evidence")
        if receipt.status is HostChangeStatus.APPLIED and not receipt.after_evidence_ids:
            raise ValueError("host broker applied without after evidence")
        return receipt
