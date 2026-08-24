"""Persistent owner-private device identity and TLS credential lifecycle."""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from fam_os.fabric.credential_files import (
    UnsafeDeviceCredential,
    create_private_credential,
    fsync_directory,
    identity_lock,
    prepare_identity_root,
    verify_private_credential,
)
from fam_os.fabric.certificate_validity import certificate_valid_at
from fam_os.fabric.identity import DeviceIdentity

DEVICE_CREDENTIAL_CONTRACT_VERSION = "fam.fabric.device-credentials/v1alpha1"
_FILES = ("identity.json", "identity-key.pem", "identity-cert.pem", "tls-key.pem", "tls-chain.pem")


class DeviceIdentityRecoveryRequired(RuntimeError):
    """Raised when persistent identity material is incomplete or unsafe."""


@dataclass(frozen=True, slots=True)
class DeviceCredentialPaths:
    root: Path
    metadata: Path
    identity_key: Path
    identity_certificate: Path
    tls_key: Path
    tls_chain: Path

    @classmethod
    def beneath(cls, root: Path) -> DeviceCredentialPaths:
        return cls(
            root, root / "identity.json", root / "identity-key.pem",
            root / "identity-cert.pem", root / "tls-key.pem", root / "tls-chain.pem",
        )


@dataclass(frozen=True, slots=True)
class PersistentDeviceCredentials:
    identity: DeviceIdentity
    identity_key: Ed25519PrivateKey
    identity_certificate: x509.Certificate
    tls_key: Ed25519PrivateKey
    tls_certificate: x509.Certificate
    paths: DeviceCredentialPaths
    contract_version: str = DEVICE_CREDENTIAL_CONTRACT_VERSION

    @property
    def identity_certificate_base64(self) -> str:
        value = self.identity_certificate.public_bytes(serialization.Encoding.DER)
        return base64.b64encode(value).decode("ascii")


class PersistentDeviceIdentityStore:
    def __init__(self, root: Path, owner_uid: int, *, now=None) -> None:
        self._paths = DeviceCredentialPaths.beneath(root)
        self._owner_uid = owner_uid
        self._now = now or (lambda: datetime.now(UTC))

    def resolve(self, display_name: str) -> PersistentDeviceCredentials:
        _validate_display_name(display_name)
        try:
            prepare_identity_root(self._paths.root, self._owner_uid)
        except UnsafeDeviceCredential as error:
            raise DeviceIdentityRecoveryRequired(str(error)) from error
        try:
            with identity_lock(self._paths.root / "identity.lock", self._owner_uid):
                present = tuple(
                    path.exists() or path.is_symlink() for path in self._credential_paths()
                )
                if any(present) and not all(present):
                    raise DeviceIdentityRecoveryRequired("device identity material is incomplete")
                if not any(present):
                    self._create(display_name)
                return self._load(display_name)
        except UnsafeDeviceCredential as error:
            raise DeviceIdentityRecoveryRequired(str(error)) from error

    def _credential_paths(self) -> tuple[Path, ...]:
        return tuple(self._paths.root / name for name in _FILES)

    def _create(self, display_name: str) -> None:
        now = self._now()
        identity_key = Ed25519PrivateKey.generate()
        identity = _device_identity(identity_key.public_key(), display_name)
        identity_cert = _identity_certificate(identity, identity_key, now)
        tls_key = Ed25519PrivateKey.generate()
        tls_cert = _tls_certificate(identity, tls_key.public_key(), identity_cert, identity_key, now)
        documents = {
            self._paths.identity_key: _private_key_pem(identity_key),
            self._paths.identity_certificate: identity_cert.public_bytes(serialization.Encoding.PEM),
            self._paths.tls_key: _private_key_pem(tls_key),
            self._paths.tls_chain: (
                tls_cert.public_bytes(serialization.Encoding.PEM)
                + identity_cert.public_bytes(serialization.Encoding.PEM)
            ),
            self._paths.metadata: _identity_json(identity),
        }
        created: list[Path] = []
        try:
            for path, content in documents.items():
                create_private_credential(path, content)
                created.append(path)
            fsync_directory(self._paths.root)
        except BaseException:
            for path in created:
                path.unlink(missing_ok=True)
            raise

    def _load(self, display_name: str) -> PersistentDeviceCredentials:
        for path in self._credential_paths():
            try:
                verify_private_credential(path, self._owner_uid)
            except UnsafeDeviceCredential as error:
                raise DeviceIdentityRecoveryRequired(str(error)) from error
        try:
            metadata = json.loads(self._paths.metadata.read_text("utf-8"))
            identity = DeviceIdentity(
                metadata["device_id"], metadata["display_name"],
                metadata["public_key_base64"], metadata["fingerprint_sha256"],
            )
            if metadata["contract_version"] != DEVICE_CREDENTIAL_CONTRACT_VERSION:
                raise ValueError("unsupported device credential contract")
            if identity.display_name != display_name:
                raise ValueError("device display name differs from persistent identity")
            identity_key = _load_private_key(self._paths.identity_key)
            identity_cert = x509.load_pem_x509_certificate(
                self._paths.identity_certificate.read_bytes(),
            )
            tls_key = _load_private_key(self._paths.tls_key)
            tls_cert = x509.load_pem_x509_certificate(self._paths.tls_chain.read_bytes())
            _validate_credentials(identity, identity_key, identity_cert, tls_key, tls_cert, self._now())
        except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise DeviceIdentityRecoveryRequired("device identity material is corrupt") from error
        return PersistentDeviceCredentials(
            identity, identity_key, identity_cert, tls_key, tls_cert, self._paths,
        )


def _device_identity(public_key: Ed25519PublicKey, display_name: str) -> DeviceIdentity:
    raw = public_key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    fingerprint = hashlib.sha256(raw).hexdigest()
    return DeviceIdentity(
        "device-" + fingerprint[:24], display_name,
        base64.b64encode(raw).decode("ascii"), fingerprint,
    )


def _identity_certificate(
    identity: DeviceIdentity, key: Ed25519PrivateKey, now: datetime,
) -> x509.Certificate:
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, identity.device_id)])
    return (
        x509.CertificateBuilder().subject_name(subject).issuer_name(subject)
        .public_key(key.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5)).not_valid_after(now + timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(x509.KeyUsage(True, False, False, False, False, True, True, False, False), critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), False)
        .add_extension(_device_san(identity.device_id), critical=False).sign(key, algorithm=None)
    )


def _tls_certificate(
    identity: DeviceIdentity, public_key: Ed25519PublicKey,
    issuer: x509.Certificate, issuer_key: Ed25519PrivateKey, now: datetime,
) -> x509.Certificate:
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, identity.device_id + ".tls")])
    return (
        x509.CertificateBuilder().subject_name(subject).issuer_name(issuer.subject)
        .public_key(public_key).serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5)).not_valid_after(now + timedelta(days=730))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.KeyUsage(True, False, False, False, False, False, False, False, False), critical=True)
        .add_extension(x509.ExtendedKeyUsage(
            [ExtendedKeyUsageOID.CLIENT_AUTH, ExtendedKeyUsageOID.SERVER_AUTH],
        ), critical=False)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(public_key), False)
        .add_extension(_device_san(identity.device_id), critical=False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(issuer_key.public_key()), False)
        .sign(issuer_key, algorithm=None)
    )


def _validate_credentials(identity, identity_key, identity_cert, tls_key, tls_cert, now) -> None:
    if _raw_public(identity_key.public_key()) != base64.b64decode(identity.public_key_base64):
        raise ValueError("identity private key does not match metadata")
    if _raw_public(identity_cert.public_key()) != _raw_public(identity_key.public_key()):
        raise ValueError("identity certificate does not match key")
    identity_cert.public_key().verify(identity_cert.signature, identity_cert.tbs_certificate_bytes)
    identity_cert.public_key().verify(tls_cert.signature, tls_cert.tbs_certificate_bytes)
    if _raw_public(tls_cert.public_key()) != _raw_public(tls_key.public_key()):
        raise ValueError("TLS certificate does not match key")
    if tls_cert.issuer != identity_cert.subject or _san_device(tls_cert) != identity.device_id:
        raise ValueError("TLS certificate is not bound to device identity")
    if _san_device(identity_cert) != identity.device_id:
        raise ValueError("identity certificate has the wrong device binding")
    if not certificate_valid_at(identity_cert, now):
        raise ValueError("identity certificate is outside its validity period")
    if not certificate_valid_at(tls_cert, now):
        raise ValueError("TLS certificate is outside its validity period")


def _device_san(device_id: str) -> x509.SubjectAlternativeName:
    return x509.SubjectAlternativeName([x509.UniformResourceIdentifier("urn:fam-os:" + device_id)])


def _san_device(certificate: x509.Certificate) -> str:
    values = certificate.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    uris = values.get_values_for_type(x509.UniformResourceIdentifier)
    if len(uris) != 1 or not uris[0].startswith("urn:fam-os:device-"):
        raise ValueError("certificate device SAN is invalid")
    return uris[0].removeprefix("urn:fam-os:")


def _identity_json(identity: DeviceIdentity) -> bytes:
    value = {
        "contract_version": DEVICE_CREDENTIAL_CONTRACT_VERSION,
        "device_id": identity.device_id,
        "display_name": identity.display_name,
        "fingerprint_sha256": identity.fingerprint_sha256,
        "public_key_base64": identity.public_key_base64,
    }
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _private_key_pem(key: Ed25519PrivateKey) -> bytes:
    return key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )


def _load_private_key(path: Path) -> Ed25519PrivateKey:
    key = serialization.load_pem_private_key(path.read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise TypeError("device keys must be Ed25519")
    return key


def _raw_public(key) -> bytes:
    if not isinstance(key, Ed25519PublicKey):
        raise TypeError("device public keys must be Ed25519")
    return key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def _validate_display_name(value: str) -> None:
    if not 1 <= len(value.strip()) <= 64 or any(ord(character) < 32 for character in value):
        raise ValueError("device display name is invalid")
