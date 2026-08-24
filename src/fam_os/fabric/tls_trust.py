"""Mutual-TLS contexts and post-handshake device identity binding."""

from __future__ import annotations

import hashlib
import ssl
from dataclasses import dataclass
from datetime import UTC, datetime

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from fam_os.fabric.credentials import PersistentDeviceCredentials
from fam_os.fabric.certificate_validity import certificate_valid_at
from fam_os.fabric.pairing import DevicePairingApproval, verify_pairing_approval
from fam_os.fabric.pairing_certificates import (
    certificate_device,
    validate_identity_certificate,
)

MUTUAL_TLS_CONTRACT_VERSION = "fam.fabric.mutual-tls/v1alpha1"


@dataclass(frozen=True, slots=True)
class AuthenticatedPeer:
    device_id: str
    display_name: str
    owner_id: str
    certificate_sha256: str
    tls_version: str
    contract_version: str = MUTUAL_TLS_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if not self.device_id or not self.owner_id or len(self.certificate_sha256) != 64:
            raise ValueError("authenticated peer identity is invalid")
        int(self.certificate_sha256, 16)
        if self.tls_version != "TLSv1.3":
            raise ValueError("authenticated peer transport is not TLS 1.3")


class PairedPeerTrust:
    def __init__(
        self,
        credentials: PersistentDeviceCredentials,
        approvals: tuple[DevicePairingApproval, ...],
        owner_id: str,
        *,
        now=None,
    ) -> None:
        if not owner_id.strip():
            raise ValueError("peer trust owner must not be empty")
        self.credentials = credentials
        self.owner_id = owner_id
        self._now = now or (lambda: datetime.now(UTC))
        peers: dict[str, DevicePairingApproval] = {}
        roots: dict[str, x509.Certificate] = {}
        for approval in approvals:
            root = self._validate_approval(approval)
            peer_id = approval.peer_identity.device_id
            if peer_id in peers:
                raise ValueError("peer trust contains a duplicate device")
            peers[peer_id] = approval
            roots[peer_id] = root
        if not peers:
            raise ValueError("mutual TLS requires at least one explicitly paired peer")
        self._peers = peers
        self._roots = roots

    def approval(self, device_id: str) -> DevicePairingApproval:
        try:
            return self._peers[device_id]
        except KeyError as error:
            raise PermissionError("TLS peer is not explicitly paired") from error

    def server_context(self) -> ssl.SSLContext:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self._configure(context)
        return context

    def client_context(self) -> ssl.SSLContext:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        self._configure(context)
        return context

    def authenticate(
        self,
        connection: ssl.SSLSocket,
        *,
        expected_device_id: str | None = None,
    ) -> AuthenticatedPeer:
        certificate_der = connection.getpeercert(binary_form=True)
        if not certificate_der:
            raise PermissionError("TLS peer did not present a certificate")
        certificate = x509.load_der_x509_certificate(certificate_der)
        device_id = certificate_device(certificate)
        if expected_device_id is not None and device_id != expected_device_id:
            raise PermissionError("TLS peer identity differs from the requested device")
        approval = self.approval(device_id)
        root = validate_identity_certificate(
            approval.peer_identity, approval.peer_identity_certificate_base64,
            observed_at=self._now(),
        )
        if certificate.issuer != root.subject:
            raise PermissionError("TLS leaf issuer differs from the paired identity")
        root_public = root.public_key()
        if not isinstance(root_public, Ed25519PublicKey):
            raise PermissionError("paired TLS root is not Ed25519")
        root_public.verify(certificate.signature, certificate.tbs_certificate_bytes)
        now = self._now()
        if not certificate_valid_at(certificate, now):
            raise PermissionError("TLS peer leaf certificate is expired")
        version = connection.version() or ""
        return AuthenticatedPeer(
            device_id, approval.peer_identity.display_name, approval.owner_id,
            hashlib.sha256(certificate_der).hexdigest(), version,
        )

    def _validate_approval(self, approval: DevicePairingApproval) -> x509.Certificate:
        if approval.local_device_id != self.credentials.identity.device_id:
            raise ValueError("pairing approval belongs to another local identity")
        if approval.owner_id != self.owner_id:
            raise PermissionError("pairing approval belongs to another owner")
        verify_pairing_approval(approval, self.credentials.identity)
        return validate_identity_certificate(
            approval.peer_identity, approval.peer_identity_certificate_base64,
            observed_at=self._now(),
        )

    def _configure(self, context: ssl.SSLContext) -> None:
        context.minimum_version = ssl.TLSVersion.TLSv1_3
        context.maximum_version = ssl.TLSVersion.TLSv1_3
        context.verify_mode = ssl.CERT_REQUIRED
        context.verify_flags |= ssl.VERIFY_X509_STRICT
        context.load_cert_chain(
            str(self.credentials.paths.tls_chain), str(self.credentials.paths.tls_key),
        )
        authorities = "".join(
            root.public_bytes(serialization.Encoding.PEM).decode("ascii")
            for root in self._roots.values()
        )
        context.load_verify_locations(cadata=authorities)
