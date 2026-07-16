import os
import unittest

from fam_os.adapters.linux.screen_input.x11_inspector import (
    X11InspectorSettings, X11WindowInspector,
)
from fam_os.adapters.linux.screen_input.x11_provider import X11ScreenInputProvider
from fam_os.adapters.linux.x11_windows import X11WindowDiscovery, X11WindowSettings
from fam_os.applications import ScreenTarget


class LiveX11ScreenInputTests(unittest.TestCase):
    def test_active_window_metadata_only_without_capture_or_input(self):
        session_type = os.environ.get("XDG_SESSION_TYPE", "")
        display = os.environ.get("DISPLAY", "")
        if session_type.casefold() != "x11" or not display:
            self.skipTest("X11 desktop is unavailable")
        discovered = X11WindowDiscovery(
            X11WindowSettings(session_type, True, include_titles=False)
        ).discover()
        window = next(
            (item for item in discovered.windows if item.window_id == discovered.focused_window_id),
            None,
        )
        if window is None or window.process_id is None:
            self.skipTest("focused X11 process identity is unavailable")
        target = ScreenTarget("live.desktop.application", window.process_id, window.window_id)
        settings = X11InspectorSettings(session_type, display)
        state = X11WindowInspector(settings).inspect(target)
        self.assertIsNotNone(state)
        self.assertTrue(state.focused)
        self.assertEqual((window.window_id, window.process_id), (state.window_id, state.process_id))
        self.assertGreater(state.width * state.height, 0)
        provider = X11ScreenInputProvider(settings)
        self.assertTrue(provider.input_available())
        try:
            import PIL  # noqa: F401
        except ImportError:
            self.assertFalse(provider.capture_available())
        else:
            self.assertTrue(provider.capture_available())


if __name__ == "__main__":
    unittest.main()
