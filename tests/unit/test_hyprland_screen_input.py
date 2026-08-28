import json
import subprocess
import unittest

from fam_os.adapters.linux.screen_input.types import ProviderInputAction
from fam_os.adapters.wayland.screen_input import (
    HyprlandScreenInputProvider, HyprlandScreenInputSettings,
    parse_hyprland_screen_state,
)
from fam_os.applications import (
    RelativeScreenPoint, ScreenInputInstruction, ScreenInputKind, ScreenTarget,
)


class _Runner:
    def __init__(self):
        self.commands = []

    def run(self, command, timeout_seconds=10):
        self.commands.append(command)
        if command[-1] == "clients":
            return _clients()
        if command[-1] == "activewindow":
            return json.dumps({"address": "0xabc"})
        return "ok"


class HyprlandScreenInputTests(unittest.TestCase):
    def test_parses_exact_focused_window_geometry(self):
        target = ScreenTarget("calculator", 42, "0xabc")
        state = parse_hyprland_screen_state(
            target, _clients(), json.dumps({"address": "0xabc"}),
        )
        self.assertEqual((10, 20, 800, 600), (
            state.x, state.y, state.width, state.height,
        ))
        self.assertTrue(state.focused)

    def test_captures_window_and_injects_relative_click(self):
        runner = _Runner()
        commands = []
        png = (
            b"\x89PNG\r\n\x1a\n" + b"\0" * 8
            + (800).to_bytes(4, "big") + (600).to_bytes(4, "big")
        )

        def run(command, **kwargs):
            commands.append(command)
            output = png if command[0] == "/usr/bin/grim" else ""
            return subprocess.CompletedProcess(command, 0, output, "")

        paths = {
            name: "/usr/bin/" + name
            for name in ("grim", "hyprctl", "wtype", "ydotool")
        }
        provider = HyprlandScreenInputProvider(
            HyprlandScreenInputSettings("wayland", True), runner=runner,
            run_binary=run, which=paths.get,
        )
        target = ScreenTarget("calculator", 42, "0xabc")
        frame = provider.capture(target, 1_000_000, 1_000_000, 1024)
        self.assertEqual((800, 600), (frame.encoded_width, frame.encoded_height))
        instruction = ScreenInputInstruction(
            ScreenInputKind.POINTER_CLICK,
            RelativeScreenPoint(500_000, 500_000),
        )
        self.assertTrue(provider.inject(
            target, ProviderInputAction(frame.state, instruction),
        ))
        self.assertIn(
            ("hyprctl", "dispatch", "movecursor", "410", "320"),
            runner.commands,
        )
        self.assertIn(("/usr/bin/ydotool", "click", "0xC0"), commands)


def _clients():
    return json.dumps([{
        "address": "0xabc", "pid": 42, "at": [10, 20], "size": [800, 600],
    }])


if __name__ == "__main__":
    unittest.main()
