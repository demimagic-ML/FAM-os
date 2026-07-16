"""Capture strict privacy-reviewed workstation resource documents."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from fam_os.adapters.linux import (
    LinuxHardwareDiscovery,
    LinuxPaths,
    PrivacyReviewedLinuxResourceDiscovery,
)
from fam_os.adapters.linux.command import SubprocessCommandRunner
from fam_os.adapters.linux.host import StandardLibraryHostProbe
from fam_os.scheduler import (
    ComposedResourceConfiguration,
    ConfigurationCompositionRequest,
    DiscoveredResourceState,
    SchedulerDefaults,
    StorageMedium,
    ValidationProfileDocument,
    compose_resource_configuration,
)
from fam_os.schemas import encode_document, loads_document


@dataclass(frozen=True, slots=True)
class WorkstationCapture:
    directory: Path
    discovered_state: DiscoveredResourceState
    composition: ComposedResourceConfiguration

    @property
    def budget_path(self) -> Path:
        return self.directory / "effective-budget.json"


def capture_live_workstation(
    profile_path: Path,
    output_root: Path,
    storage_medium: StorageMedium = StorageMedium.NVME,
) -> WorkstationCapture:
    captured_at = datetime.now(timezone.utc)
    capture_id = captured_at.strftime("%Y%m%dT%H%M%S%fZ")
    runner = SubprocessCommandRunner()
    hardware = LinuxHardwareDiscovery(
        LinuxPaths(), runner, StandardLibraryHostProbe()
    )
    discovery = PrivacyReviewedLinuxResourceDiscovery(
        hardware,
        runner,
        f"inventory.{capture_id}",
        f"state.{capture_id}",
        storage_medium,
    ).collect()
    profile = _load_profile(profile_path)
    composition = _compose(profile, discovery, capture_id)
    directory = output_root / capture_id
    _write_capture(directory, profile_path, discovery, composition)
    return WorkstationCapture(directory, discovery, composition)


def _load_profile(path: Path) -> ValidationProfileDocument:
    value = loads_document(path.read_text(encoding="utf-8"))
    if not isinstance(value, ValidationProfileDocument):
        raise TypeError("profile path did not decode to a validation profile")
    return value


def _compose(
    profile: ValidationProfileDocument,
    discovery: DiscoveredResourceState,
    capture_id: str,
) -> ComposedResourceConfiguration:
    defaults = SchedulerDefaults(
        f"defaults.capture.{capture_id}",
        profile.configuration.profile,
        profile.configuration.policy,
    )
    request = ConfigurationCompositionRequest(
        f"budget.{capture_id}", defaults, discovery, profile.configuration
    )
    return compose_resource_configuration(request)


def _write_capture(
    directory: Path,
    profile_path: Path,
    discovery: DiscoveredResourceState,
    composition: ComposedResourceConfiguration,
) -> None:
    directory.mkdir(parents=True, exist_ok=False)
    _write_json(directory / "host-inventory.json", encode_document(discovery.inventory))
    _write_json(directory / "discovered-state.json", encode_document(discovery))
    _write_json(directory / "effective-budget.json", encode_document(composition.budget))
    _write_json(directory / "composition.json", encode_document(composition))
    _write_json(directory / "privacy-review.json", _privacy_review(profile_path, discovery))


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _privacy_review(
    profile_path: Path, discovery: DiscoveredResourceState
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "review_status": "passed",
        "profile_filename": profile_path.name,
        "inventory_id": discovery.inventory.inventory_id,
        "state_id": discovery.state_id,
        "retained_fields": [
            "os_name_and_release",
            "cpu_architecture_model_and_counts",
            "memory_capacity_and_availability",
            "storage_capacity_medium_and_availability",
            "accelerator_model_driver_capacity_and_usage",
        ],
        "excluded_fields": [
            "hostname",
            "username",
            "home_directory",
            "mount_path",
            "block_device_path",
            "storage_serial",
            "gpu_uuid",
            "gpu_pci_bus_id",
            "npu_device_path",
        ],
        "opaque_identifiers": [
            "inventory_id",
            "state_id",
            "gpu-N",
            "npu-N",
            "storage-root",
        ],
    }
