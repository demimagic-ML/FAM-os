"""Generic Wayland adapters."""

from fam_os.adapters.wayland.windows import GenericWaylandWindowDiscovery
from fam_os.adapters.wayland.screen_input import (
    HyprlandScreenInputProvider, HyprlandScreenInputSettings,
    default_hyprland_screen_input_provider,
)

__all__ = [
    "GenericWaylandWindowDiscovery", "HyprlandScreenInputProvider",
    "HyprlandScreenInputSettings", "default_hyprland_screen_input_provider",
]
