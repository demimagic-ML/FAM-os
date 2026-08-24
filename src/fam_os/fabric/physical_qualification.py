"""Content-free identity and hardware evidence for physical fabric qualification."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from fam_os.fabric.credentials import PersistentDeviceCredentials


PHYSICAL_HOST_EVIDENCE_VERSION = "fam.fabric.physical-host-evidence/v1alpha1"
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,255}$")


class PhysicalHostRole(StrEnum):
    REQUESTER = "requester"
    EXPERT_PEER = "expert_peer"


class HardwareAnchorKind(StrEnum):
    DMI_PRODUCT_UUID = "dmi_product_uuid"
    DEVICE_TREE_SERIAL = "device_tree_serial"
    BLOCK_DEVICE_SERIAL = "block_device_serial"


@dataclass(frozen=True, slots=True)
class PhysicalHostEvidence:
    evidence_id: str
    qualification_id: str
    role: PhysicalHostRole
    device_id: str
    device_public_key_base64: str
    device_fingerprint_sha256: str
    machine_id_sha256: str
    hardware_anchor_kind: HardwareAnchorKind
    hardware_anchor_sha256: str
    hostname_sha256: str
    kernel_release: str
    architecture: str
    virtualization_kind: str
    physical_host: bool
    cpu_threads: int
    memory_bytes: int
    block_device_bytes: int
    network_interface_count: int
    non_loopback_address_sha256: tuple[str, ...]
    release_id: str
    signer_key_id: str
    release_manifest_sha256: str
    release_component_count: int
    installation_healthy: bool
    captured_at: datetime
    signature_base64: str
    contract_version: str = PHYSICAL_HOST_EVIDENCE_VERSION

    def __post_init__(self) -> None:
        for name in (
            "evidence_id", "qualification_id", "device_id", "kernel_release",
            "architecture", "virtualization_kind", "release_id", "signer_key_id",
        ):
            _text(getattr(self, name), name)
        for name in (
            "device_fingerprint_sha256", "machine_id_sha256",
            "hardware_anchor_sha256", "hostname_sha256",
            "release_manifest_sha256",
        ):
            _digest(getattr(self, name), name)
        try:
            public_key = base64.b64decode(
                self.device_public_key_base64, validate=True,
            )
        except (binascii.Error, TypeError, ValueError) as error:
            raise ValueError("physical host device public key is invalid") from error
        if (
            len(public_key) != 32
            or hashlib.sha256(public_key).hexdigest()
            != self.device_fingerprint_sha256
            or self.device_id != "device-" + self.device_fingerprint_sha256[:24]
        ):
            raise ValueError("physical host device identity binding is invalid")
        if not isinstance(self.role, PhysicalHostRole):
            raise TypeError("physical host role is invalid")
        if not isinstance(self.hardware_anchor_kind, HardwareAnchorKind):
            raise TypeError("physical hardware anchor kind is invalid")
        if self.physical_host != (self.virtualization_kind == "none"):
            raise ValueError("physical host and virtualization evidence disagree")
        for name in (
            "cpu_threads", "memory_bytes", "block_device_bytes",
            "network_interface_count", "release_component_count",
        ):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise ValueError(f"physical host {name} must be positive")
        if (
            not self.non_loopback_address_sha256
            or len(set(self.non_loopback_address_sha256))
            != len(self.non_loopback_address_sha256)
        ):
            raise ValueError("physical host needs unique non-loopback network evidence")
        for digest in self.non_loopback_address_sha256:
            _digest(digest, "network address")
        if not isinstance(self.installation_healthy, bool):
            raise TypeError("physical host installation health is invalid")
        if self.captured_at.tzinfo is None or self.captured_at.utcoffset() is None:
            raise ValueError("physical host capture time must be timezone-aware")
        _signature(self.signature_base64)
        if self.contract_version != PHYSICAL_HOST_EVIDENCE_VERSION:
            raise ValueError("physical host evidence contract is unsupported")


def create_physical_host_evidence(
    credentials: PersistentDeviceCredentials,
    *,
    evidence_id: str,
    qualification_id: str,
    role: PhysicalHostRole,
    machine_id_sha256: str,
    hardware_anchor_kind: HardwareAnchorKind,
    hardware_anchor_sha256: str,
    hostname_sha256: str,
    kernel_release: str,
    architecture: str,
    virtualization_kind: str,
    physical_host: bool,
    cpu_threads: int,
    memory_bytes: int,
    block_device_bytes: int,
    network_interface_count: int,
    non_loopback_address_sha256: tuple[str, ...],
    release_id: str,
    signer_key_id: str,
    release_manifest_sha256: str,
    release_component_count: int,
    installation_healthy: bool,
    captured_at: datetime,
) -> PhysicalHostEvidence:
    identity = credentials.identity
    values: dict[str, object] = {
        "evidence_id": evidence_id,
        "qualification_id": qualification_id,
        "role": role,
        "device_id": identity.device_id,
        "device_public_key_base64": identity.public_key_base64,
        "device_fingerprint_sha256": identity.fingerprint_sha256,
        "machine_id_sha256": machine_id_sha256,
        "hardware_anchor_kind": hardware_anchor_kind,
        "hardware_anchor_sha256": hardware_anchor_sha256,
        "hostname_sha256": hostname_sha256,
        "kernel_release": kernel_release,
        "architecture": architecture,
        "virtualization_kind": virtualization_kind,
        "physical_host": physical_host,
        "cpu_threads": cpu_threads,
        "memory_bytes": memory_bytes,
        "block_device_bytes": block_device_bytes,
        "network_interface_count": network_interface_count,
        "non_loopback_address_sha256": non_loopback_address_sha256,
        "release_id": release_id,
        "signer_key_id": signer_key_id,
        "release_manifest_sha256": release_manifest_sha256,
        "release_component_count": release_component_count,
        "installation_healthy": installation_healthy,
        "captured_at": captured_at,
    }
    signature = credentials.identity_key.sign(_signature_payload(values))
    return PhysicalHostEvidence(
        evidence_id=evidence_id,
        qualification_id=qualification_id,
        role=role,
        device_id=identity.device_id,
        device_public_key_base64=identity.public_key_base64,
        device_fingerprint_sha256=identity.fingerprint_sha256,
        machine_id_sha256=machine_id_sha256,
        hardware_anchor_kind=hardware_anchor_kind,
        hardware_anchor_sha256=hardware_anchor_sha256,
        hostname_sha256=hostname_sha256,
        kernel_release=kernel_release,
        architecture=architecture,
        virtualization_kind=virtualization_kind,
        physical_host=physical_host,
        cpu_threads=cpu_threads,
        memory_bytes=memory_bytes,
        block_device_bytes=block_device_bytes,
        network_interface_count=network_interface_count,
        non_loopback_address_sha256=non_loopback_address_sha256,
        release_id=release_id,
        signer_key_id=signer_key_id,
        release_manifest_sha256=release_manifest_sha256,
        release_component_count=release_component_count,
        installation_healthy=installation_healthy,
        captured_at=captured_at,
        signature_base64=base64.b64encode(signature).decode("ascii"),
    )


def verify_physical_host_evidence(value: PhysicalHostEvidence) -> None:
    public_key = Ed25519PublicKey.from_public_bytes(
        base64.b64decode(value.device_public_key_base64, validate=True),
    )
    values = {
        name: getattr(value, name)
        for name in value.__dataclass_fields__
        if name not in {"signature_base64", "contract_version"}
    }
    try:
        public_key.verify(
            base64.b64decode(value.signature_base64, validate=True),
            _signature_payload(values),
        )
    except (InvalidSignature, TypeError, ValueError, binascii.Error) as error:
        raise ValueError("physical host evidence signature is invalid") from error


def _text(value: str, name: str) -> None:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise ValueError(f"physical host {name} is invalid")


def _digest(value: str, name: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError(f"physical host {name} is not lowercase SHA-256")


def _signature(value: str) -> None:
    try:
        decoded = base64.b64decode(value, validate=True)
    except (binascii.Error, TypeError, ValueError) as error:
        raise ValueError("physical host signature is invalid") from error
    if len(decoded) != 64:
        raise ValueError("physical host signature is invalid")


def _signature_payload(values: dict) -> bytes:
    def normalized(value):
        if isinstance(value, StrEnum):
            return value.value
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, tuple):
            return [normalized(item) for item in value]
        return value

    document = {
        "contract_version": PHYSICAL_HOST_EVIDENCE_VERSION,
        **{name: normalized(value) for name, value in values.items()},
    }
    return json.dumps(
        document, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
