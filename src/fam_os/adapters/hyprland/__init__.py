"""Hyprland desktop observation and control adapters."""

from fam_os.adapters.hyprland.windows import (
    HyprlandMonitor,
    HyprlandWindowDiscovery,
    HyprlandWindowSettings,
    parse_active_window,
    parse_clients,
    parse_monitors,
)

__all__ = [
    "HyprlandMonitor", "HyprlandWindowDiscovery", "HyprlandWindowSettings",
    "parse_active_window", "parse_clients", "parse_monitors",
]
