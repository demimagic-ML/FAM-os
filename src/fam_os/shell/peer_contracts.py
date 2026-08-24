"""Bounded Shell contracts for owner-visible trusted peer management."""

from dataclasses import dataclass
from enum import StrEnum

from fam_os.fabric import (
    PeerManagementReceipt,
    RemoteContextDisclosureEvidence,
    TrustedPeerDirectoryEntry,
)

SHELL_PEER_CONTRACT_VERSION = "fam.shell.peer/v1alpha1"
MAX_SHELL_PEER_PAGE = 100


class ShellPeerOperation(StrEnum):
    PEERS = "peers"
    PROBE = "probe"
    RECEIPTS = "receipts"
    CONTEXT = "context"
    CONTEXT_EVIDENCE = "context_evidence"


@dataclass(frozen=True, slots=True)
class ShellPeerQuery:
    request_id: str
    operation: ShellPeerOperation
    offset: int = 0
    limit: int = MAX_SHELL_PEER_PAGE
    contract_version: str = SHELL_PEER_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _text(self.request_id)
        if self.operation not in {
            ShellPeerOperation.PEERS,
            ShellPeerOperation.RECEIPTS,
            ShellPeerOperation.CONTEXT_EVIDENCE,
        }:
            raise ValueError("Shell peer query operation is invalid")
        _page(self.offset, self.limit)
        if self.contract_version != SHELL_PEER_CONTRACT_VERSION:
            raise ValueError("unsupported Shell peer contract")


@dataclass(frozen=True, slots=True)
class ShellPeerProbeRequest:
    request_id: str
    enrollment_id: str
    contract_version: str = SHELL_PEER_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _text(self.request_id)
        _text(self.enrollment_id)
        if self.contract_version != SHELL_PEER_CONTRACT_VERSION:
            raise ValueError("unsupported Shell peer contract")


@dataclass(frozen=True, slots=True)
class ShellPeerResponse:
    request_id: str
    operation: ShellPeerOperation
    offset: int
    total_count: int
    peers: tuple[TrustedPeerDirectoryEntry, ...] = ()
    control_receipts: tuple[PeerManagementReceipt, ...] = ()
    context_evidence: tuple[RemoteContextDisclosureEvidence, ...] = ()
    contract_version: str = SHELL_PEER_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _text(self.request_id)
        _page(self.offset, max(
            1, len(self.peers), len(self.control_receipts), len(self.context_evidence),
        ))
        count = len(self.peers) + len(self.control_receipts) + len(self.context_evidence)
        if self.total_count < count:
            raise ValueError("Shell peer response count is invalid")
        expected = {
            ShellPeerOperation.PEERS: (
                not self.control_receipts and not self.context_evidence
            ),
            ShellPeerOperation.PROBE: (
                len(self.peers) == 1 and self.total_count == 1
                and not self.control_receipts and not self.context_evidence
            ),
            ShellPeerOperation.RECEIPTS: not self.peers and not self.context_evidence,
            ShellPeerOperation.CONTEXT: (
                len(self.context_evidence) == 1 and self.total_count == 1
                and not self.peers and not self.control_receipts
            ),
            ShellPeerOperation.CONTEXT_EVIDENCE: (
                not self.peers and not self.control_receipts
            ),
        }[self.operation]
        if not expected or sum(bool(value) for value in (
            self.peers, self.control_receipts, self.context_evidence,
        )) > 1:
            raise ValueError("Shell peer response shape is invalid")
        if self.contract_version != SHELL_PEER_CONTRACT_VERSION:
            raise ValueError("unsupported Shell peer contract")


def _page(offset: int, limit: int) -> None:
    if isinstance(offset, bool) or offset < 0:
        raise ValueError("Shell peer offset is invalid")
    if isinstance(limit, bool) or not 1 <= limit <= MAX_SHELL_PEER_PAGE:
        raise ValueError("Shell peer limit is invalid")


def _text(value: str) -> None:
    if not value.strip():
        raise ValueError("Shell peer identity is invalid")
