import unittest
from unittest.mock import patch

from fam_os.adapters.linux.screen_input.pillow_capture import PillowPngCapture
from fam_os.adapters.linux.screen_input.types import (
    ProviderInputAction, ProviderWindowState,
)
from fam_os.adapters.linux.screen_input.x11_inspector import parse_window_state
from fam_os.adapters.linux.screen_input.x11_provider import X11ScreenInputProvider
from fam_os.adapters.linux.screen_input.x11_inspector import X11InspectorSettings
from fam_os.applications import (
    RelativeScreenPoint, ScreenInputInstruction, ScreenInputKind, ScreenTarget,
)


TARGET = ScreenTarget("org.example.Editor", 42, "0x2a")
STATE = ProviderWindowState("0x2a", 42, 100, 200, 800, 600, True)


class Inspector:
    def __init__(self, states=(STATE,)):
        self.states = list(states)

    def available(self):
        return True

    def inspect(self, target):
        return self.states.pop(0) if len(self.states) > 1 else self.states[0]


class Capture:
    def available(self):
        return True

    def grab(self, state, maximum_source_pixels, maximum_pixels, maximum_bytes):
        return 400, 300, b"\x89PNG\r\n\x1a\nframe"


class Input:
    def __init__(self):
        self.calls = []

    def available(self):
        return True

    def click(self, x, y):
        self.calls.append(("click", x, y))
        return True

    def key_chord(self, keys):
        self.calls.append(("keys", keys))
        return True


class X11ProviderTests(unittest.TestCase):
    def test_parser_requires_viewable_window_and_marks_exact_focus(self):
        active = "_NET_ACTIVE_WINDOW(WINDOW): window id # 0x2a\n"
        properties = "_NET_WM_PID(CARDINAL) = 42\n"
        geometry = """Absolute upper-left X:  100
Absolute upper-left Y:  200
Width: 800
Height: 600
Map State: IsViewable
"""
        self.assertEqual(STATE, parse_window_state("0x2a", active, properties, geometry))
        self.assertIsNone(parse_window_state("0x2a", active, properties, "Width: 1"))

    def test_provider_maps_relative_click_and_rechecks_exact_state(self):
        input = Input()
        provider = X11ScreenInputProvider(
            X11InspectorSettings("x11", ":1"), Inspector(), Capture(), input,
        )
        self.assertTrue(provider.capture_available())
        self.assertTrue(provider.input_available())
        frame = provider.capture(TARGET, 1_000_000, 1_000_000, 1_000_000)
        self.assertEqual((400, 300), (frame.encoded_width, frame.encoded_height))
        instruction = ScreenInputInstruction(
            ScreenInputKind.POINTER_CLICK, RelativeScreenPoint(500_000, 250_000)
        )
        self.assertTrue(provider.inject(TARGET, ProviderInputAction(STATE, instruction)))
        self.assertEqual(("click", 500, 350), input.calls[0])

    def test_provider_refuses_input_if_geometry_or_focus_changes(self):
        changed = ProviderWindowState("0x2a", 42, 101, 200, 800, 600, True)
        input = Input()
        provider = X11ScreenInputProvider(
            X11InspectorSettings("x11", ":1"), Inspector((changed,)), Capture(), input,
        )
        chord = ScreenInputInstruction(ScreenInputKind.KEY_CHORD, keys=("Return",))
        self.assertFalse(provider.inject(TARGET, ProviderInputAction(STATE, chord)))
        self.assertEqual([], input.calls)

    def test_pillow_capture_bounds_source_and_downscales_before_encoding(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("optional Pillow capture backend is unavailable")
        image = Image.new("RGB", (800, 600), "white")
        with patch("PIL.ImageGrab.grab", return_value=image.copy()) as grab:
            width, height, encoded = PillowPngCapture(":1").grab(
                STATE, 500_000, 120_000, 1_000_000,
            )
        self.assertLessEqual(width * height, 120_000)
        self.assertTrue(encoded.startswith(b"\x89PNG\r\n\x1a\n"))
        grab.assert_called_once_with(bbox=(100, 200, 900, 800), xdisplay=":1")
        with self.assertRaisesRegex(RuntimeError, "source window"):
            PillowPngCapture(":1").grab(STATE, 10, 10, 1_000)


if __name__ == "__main__":
    unittest.main()
