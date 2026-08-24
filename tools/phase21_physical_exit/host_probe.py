"""Capture content-free physical-host and installed-release evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--installed-python", type=Path, required=True)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--prefix", type=Path, required=True)
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--device-name", required=True)
    parser.add_argument("--qualification-id", required=True)
    parser.add_argument("--role", choices=("requester", "expert_peer"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    _installed_imports(args.installed_python, args.repository)

    from fam_os.fabric import (
        HardwareAnchorKind,
        PhysicalHostRole,
        PersistentDeviceIdentityStore,
        create_physical_host_evidence,
        verify_physical_host_evidence,
    )
    from fam_os.product.bundle_installation import SignedBundleInstallation
    from fam_os.product.update_contracts import SignedReleaseManifest
    from fam_os.schemas import dumps_document, loads_document

    prefix = args.prefix.resolve()
    diagnosis = SignedBundleInstallation(prefix, {}).diagnose()
    manifest_bytes = (prefix / "active/release-manifest.json").read_bytes()
    manifest = loads_document(manifest_bytes.decode("utf-8"))
    if not isinstance(manifest, SignedReleaseManifest):
        raise RuntimeError("active release manifest is invalid")
    machine = _required(Path("/etc/machine-id"))
    anchor_kind, anchor = _hardware_anchor(HardwareAnchorKind)
    virtualization = _virtualization()
    addresses, interfaces = _network_addresses()
    role = PhysicalHostRole(args.role)
    credentials = PersistentDeviceIdentityStore(
        args.state_root.resolve() / "fabric/identity", os.geteuid(),
    ).resolve(args.device_name)
    evidence = create_physical_host_evidence(
        credentials,
        evidence_id=(
            "physical-host-" + _sha256(
                machine + role.value.encode() + args.qualification_id.encode(),
            )[:32]
        ),
        qualification_id=args.qualification_id,
        role=role,
        machine_id_sha256=_sha256(machine),
        hardware_anchor_kind=anchor_kind,
        hardware_anchor_sha256=_sha256(anchor),
        hostname_sha256=_sha256(platform.node().encode("utf-8")),
        kernel_release=platform.release(),
        architecture=platform.machine(),
        virtualization_kind=virtualization,
        physical_host=virtualization == "none",
        cpu_threads=os.cpu_count() or 1,
        memory_bytes=os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES"),
        block_device_bytes=_block_device_bytes(),
        network_interface_count=len(interfaces),
        non_loopback_address_sha256=tuple(sorted(
            _sha256(value.encode("utf-8")) for value in addresses
        )),
        release_id=manifest.release_id,
        signer_key_id=manifest.signer_key_id,
        release_manifest_sha256=_sha256(manifest_bytes),
        release_component_count=len(manifest.components),
        installation_healthy=diagnosis.healthy,
        captured_at=datetime.now(UTC),
    )
    verify_physical_host_evidence(evidence)
    _write_private(args.output, dumps_document(evidence) + "\n")
    return 0 if evidence.physical_host and evidence.installation_healthy else 1


def _hardware_anchor(kind_type):
    candidates = (
        (kind_type.DMI_PRODUCT_UUID, Path("/sys/class/dmi/id/product_uuid")),
        (kind_type.DEVICE_TREE_SERIAL, Path("/proc/device-tree/serial-number")),
    )
    for kind, path in candidates:
        if path.is_file():
            try:
                return kind, _required(path)
            except OSError:
                continue
    for path in sorted(Path("/sys/class/block").glob("*/device/serial")):
        if path.parts[-3].startswith(("loop", "ram", "zram")):
            continue
        try:
            serial = _required(path)
        except OSError:
            continue
        return kind_type.BLOCK_DEVICE_SERIAL, path.parts[-3].encode() + b"|" + serial
    raise RuntimeError("physical host lacks a supported hardware identity anchor")


def _virtualization() -> str:
    try:
        result = subprocess.run(
            ("systemd-detect-virt",), capture_output=True, text=True, timeout=10,
        )
    except OSError:
        return "unknown"
    value = result.stdout.strip().casefold()
    return value or "unknown"


def _network_addresses() -> tuple[tuple[str, ...], tuple[str, ...]]:
    result = subprocess.run(
        ("ip", "-j", "address", "show", "up"),
        check=True, capture_output=True, text=True, timeout=10,
    )
    values = json.loads(result.stdout)
    addresses: list[str] = []
    interfaces: set[str] = set()
    for item in values:
        name = item.get("ifname")
        if not isinstance(name, str) or name == "lo":
            continue
        for address in item.get("addr_info", ()):
            local = address.get("local")
            family = address.get("family")
            scope = address.get("scope")
            if (
                isinstance(local, str)
                and family in {"inet", "inet6"}
                and scope != "host"
            ):
                interfaces.add(name)
                addresses.append(f"{name}|{family}|{local}")
    if not addresses:
        raise RuntimeError("physical host has no active non-loopback address")
    return tuple(addresses), tuple(sorted(interfaces))


def _block_device_bytes() -> int:
    total = 0
    for path in Path("/sys/class/block").iterdir():
        name = path.name
        if name.startswith(("loop", "ram", "zram")) or (path / "partition").exists():
            continue
        try:
            total += int((path / "size").read_text().strip()) * 512
        except (OSError, ValueError):
            continue
    if total <= 0:
        raise RuntimeError("physical host has no measurable block device")
    return total


def _required(path: Path) -> bytes:
    value = path.read_bytes().strip().lower()
    if not value:
        raise RuntimeError(f"physical identity source {path} is empty")
    return value


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _write_private(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8", closefd=False) as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(descriptor)


def _installed_imports(installed_python: Path, repository: Path) -> None:
    root = repository.resolve()
    sys.path[:] = [str(installed_python.resolve())] + [
        item for item in sys.path
        if item and not Path(item).resolve().is_relative_to(root)
    ]


if __name__ == "__main__":
    raise SystemExit(main())
