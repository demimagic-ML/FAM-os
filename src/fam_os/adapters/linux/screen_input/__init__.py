"""Restricted Linux screen-observation and controlled-input adapter."""

from fam_os.adapters.linux.screen_input.bridge import ScreenInputBridge
from fam_os.adapters.linux.screen_input.policy import ScreenInputPolicy

__all__ = ["ScreenInputBridge", "ScreenInputPolicy"]
