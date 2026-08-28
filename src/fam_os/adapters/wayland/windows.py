"""Explicit generic-Wayland degradation when compositor IPC is unavailable."""

from fam_os.adapters.linux.x11_windows import WindowDiscoveryResult
from fam_os.applications import ApplicationDiscoveryIssue, DiscoverySurface


class GenericWaylandWindowDiscovery:
    def discover(self) -> WindowDiscoveryResult:
        return WindowDiscoveryResult((), None, (
            ApplicationDiscoveryIssue(
                DiscoverySurface.WINDOWS, "linux.wayland.compositor_adapter_required",
                "Window discovery requires a supported Wayland compositor adapter.",
            ),
        ))
