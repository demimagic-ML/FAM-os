"""Bounded Linux AT-SPI accessibility adapter."""

from fam_os.adapters.linux.accessibility.atspi import GiAtspiProvider
from fam_os.adapters.linux.accessibility.bridge import (
    AccessibilityBridgePolicy,
    LinuxAccessibilityBridge,
)
from fam_os.adapters.linux.accessibility.catalog import (
    accessibility_action,
    accessibility_observation,
    build_accessibility_registration,
)

__all__ = [
    "AccessibilityBridgePolicy",
    "GiAtspiProvider",
    "LinuxAccessibilityBridge",
    "accessibility_action",
    "accessibility_observation",
    "build_accessibility_registration",
]
