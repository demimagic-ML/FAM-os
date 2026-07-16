"""Read-only host NPU identity and access discovery."""

from __future__ import annotations

import os
import platform
import subprocess
from pathlib import Path

from fam_os.scheduler.npu_contracts import NpuHardwareEvidence


SYSFS_DEVICE = Path("/sys/class/accel/accel0/device")
DEVICE_NODE = Path("/dev/accel/accel0")


def collect_hardware_evidence() -> NpuHardwareEvidence:
    driver_path = (SYSFS_DEVICE / "driver").resolve()
    return NpuHardwareEvidence(
        vendor_id=_read(SYSFS_DEVICE / "vendor"),
        device_id=_read(SYSFS_DEVICE / "device"),
        device_family=_device_family(),
        kernel_driver=driver_path.name,
        kernel_module_version=_module_version(driver_path.name),
        operating_system=_operating_system(),
        kernel_release=platform.release(),
        device_node_present=DEVICE_NODE.is_char_device(),
        host_user_direct_access=os.access(DEVICE_NODE, os.R_OK | os.W_OK),
        delegated_device_access=True,
        access_mechanism="docker-device-pass-through-with-device-group",
    )


def device_group_id() -> int:
    return DEVICE_NODE.stat().st_gid


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def _device_family() -> str:
    address = SYSFS_DEVICE.resolve().name.removeprefix("0000:")
    result = subprocess.run(
        ("lspci", "-s", address), check=True, capture_output=True, text=True,
    )
    description = result.stdout.strip()
    return description.split(": ", 1)[-1]


def _module_version(name: str) -> str:
    result = subprocess.run(
        ("modinfo", "-F", "version", name), check=True,
        capture_output=True, text=True,
    )
    return result.stdout.strip()


def _operating_system() -> str:
    values = {}
    for line in Path("/etc/os-release").read_text(encoding="utf-8").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key] = value.strip('"')
    return f"{values.get('ID', 'unknown')} {values.get('VERSION_ID', 'unknown')}"
