"""Core-client boundary used by every FAM Shell presentation."""

from typing import Protocol

from fam_os.memory import (
    DocumentCorrectionRequest,
    DocumentDeletionRequest,
    DocumentExpirationRequest,
    DocumentInspection,
    DocumentManagementReceipt,
    MemoryDocumentExport,
)
from fam_os.shell.contracts import (
    ShellAskCommand,
    ShellCancelCommand,
    ShellDecisionCommand,
    ShellSessionSnapshot,
    ShellVerifiedAskCommand,
)
from fam_os.adaptation import LiveAdaptationControlRequest, LiveAdaptationControlReceipt
from fam_os.fabric import (
    PeerManagementRequest,
    PeerManagementReceipt,
    RemoteContextDisclosureEvidence,
    RemoteContextSendRequest,
)


class ShellCoreClient(Protocol):
    def ask(self, command: ShellAskCommand) -> ShellSessionSnapshot: ...

    def ask_verified(self, command: ShellVerifiedAskCommand) -> ShellSessionSnapshot: ...

    def snapshot(self, session_id: str) -> ShellSessionSnapshot: ...

    def decide(self, command: ShellDecisionCommand) -> ShellSessionSnapshot: ...

    def cancel(self, command: ShellCancelCommand) -> ShellSessionSnapshot: ...


class ShellCoreGateway(ShellCoreClient, Protocol):
    """Server-side implementation of the same narrow client surface."""


class ShellMemoryGateway(Protocol):
    """Owner-authorized persistent memory service exposed to Shell dispatch."""

    def inspections(self) -> tuple[DocumentInspection, ...]: ...

    def inspect(self, document_id: str) -> DocumentInspection: ...

    def export(self, document_id: str) -> MemoryDocumentExport: ...

    def correct(self, request: DocumentCorrectionRequest) -> DocumentManagementReceipt: ...

    def expire(self, request: DocumentExpirationRequest) -> DocumentManagementReceipt: ...

    def delete(self, request: DocumentDeletionRequest) -> DocumentManagementReceipt: ...

    def receipts(self) -> tuple[DocumentManagementReceipt, ...]: ...


class ShellAdaptationGateway(Protocol):
    """Owner-authorized live adaptation service exposed to Shell dispatch."""

    def control_state(self): ...

    def snapshots(self) -> tuple[object, ...]: ...

    def receipts(self) -> tuple[object, ...]: ...

    def health(self) -> tuple[object, ...]: ...

    def drift_reports(self) -> tuple[object, ...]: ...

    def control_receipts(self) -> tuple[LiveAdaptationControlReceipt, ...]: ...

    def apply_control(
        self, request: LiveAdaptationControlRequest,
    ) -> LiveAdaptationControlReceipt: ...


class ShellPeerGateway(Protocol):
    """Owner-authorized trusted peer service exposed to Shell dispatch."""

    def trusted_peers(self) -> tuple[object, ...]: ...

    def probe(self, enrollment_id: str): ...

    def control_receipts(self) -> tuple[PeerManagementReceipt, ...]: ...

    def apply_control(self, request: PeerManagementRequest) -> PeerManagementReceipt: ...

    def send_context(
        self, request: RemoteContextSendRequest,
    ) -> RemoteContextDisclosureEvidence: ...

    def context_evidence(self) -> tuple[RemoteContextDisclosureEvidence, ...]: ...
