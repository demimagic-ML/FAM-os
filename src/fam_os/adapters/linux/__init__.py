"""Read-only Linux hardware discovery adapter."""

from fam_os.adapters.linux.discovery import LinuxHardwareDiscovery
from fam_os.adapters.linux.paths import LinuxPaths
from fam_os.adapters.linux.resource_discovery import (
    PrivacyReviewedLinuxResourceDiscovery,
    build_privacy_reviewed_resource_state,
)
from fam_os.adapters.linux.application_discovery import (
    LinuxApplicationDiscovery, LinuxApplicationDiscoverySettings,
)
from fam_os.adapters.linux.desktop_environment import application_discovery_settings
from fam_os.adapters.linux.deterministic_catalog import (
    DeterministicCapabilityDeclaration, build_deterministic_registration,
    file_observation, file_write, mime_observation, portal_open_uri,
)
from fam_os.adapters.linux.scoped_files import ScopedFileAdapter, ScopedFilePolicy
from fam_os.adapters.linux.accessibility import (
    AccessibilityBridgePolicy, GiAtspiProvider, LinuxAccessibilityBridge,
    accessibility_action, accessibility_observation, build_accessibility_registration,
)
from fam_os.adapters.linux.live_resources import (
    CacheDirectory,
    DirectoryStorageRuntimeObserver,
    NvidiaAcceleratorRuntimeObserver,
)

__all__ = [
    "LinuxHardwareDiscovery",
    "LinuxApplicationDiscovery",
    "LinuxApplicationDiscoverySettings",
    "DeterministicCapabilityDeclaration",
    "LinuxPaths",
    "PrivacyReviewedLinuxResourceDiscovery",
    "build_privacy_reviewed_resource_state",
    "application_discovery_settings",
    "build_deterministic_registration",
    "file_observation",
    "file_write",
    "mime_observation",
    "portal_open_uri",
    "ScopedFileAdapter",
    "ScopedFilePolicy",
    "AccessibilityBridgePolicy",
    "GiAtspiProvider",
    "LinuxAccessibilityBridge",
    "accessibility_action",
    "accessibility_observation",
    "build_accessibility_registration",
    "CacheDirectory",
    "DirectoryStorageRuntimeObserver",
    "NvidiaAcceleratorRuntimeObserver",
]
