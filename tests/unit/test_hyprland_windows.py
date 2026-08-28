import json
import unittest

from fam_os.adapters.hyprland.windows import (
    HyprlandWindowDiscovery, HyprlandWindowSettings, parse_active_window,
    parse_clients, parse_monitors,
)


CLIENTS = json.dumps([
    {
        "address": "0xABC", "mapped": True, "hidden": False, "pid": 123,
        "class": "org.example.App", "title": "Example",
    },
    {"address": "0xDEF", "mapped": False, "pid": 456, "class": "hidden"},
])
ACTIVE = json.dumps({"address": "0xabc"})
MONITORS = json.dumps([
    {"id": 0, "name": "DP-1", "x": 0, "y": 0, "width": 2560,
     "height": 1440, "scale": 1.25, "focused": True},
])


class Runner:
    def run(self, command, timeout_seconds=10):
        return {
            ("hyprctl", "-j", "clients"): CLIENTS,
            ("hyprctl", "-j", "activewindow"): ACTIVE,
            ("hyprctl", "-j", "monitors"): MONITORS,
        }.get(command)


class HyprlandWindowTests(unittest.TestCase):
    def test_parses_hyprland_clients_focus_and_monitors(self):
        windows = parse_clients(CLIENTS, include_titles=True)
        monitors = parse_monitors(MONITORS)
        self.assertEqual(len(windows), 1)
        self.assertEqual(windows[0].window_id, "0xabc")
        self.assertEqual(windows[0].process_id, 123)
        self.assertEqual(windows[0].application_class, "org.example.App")
        self.assertEqual(windows[0].title, "Example")
        self.assertEqual(parse_active_window(ACTIVE), "0xabc")
        self.assertEqual(monitors[0].name, "DP-1")
        self.assertEqual(monitors[0].scale, 1.25)

    def test_hyprland_discovery_matches_existing_application_contract(self):
        discovery = HyprlandWindowDiscovery(
            HyprlandWindowSettings("wayland", True, include_titles=True), Runner(),
        )
        result = discovery.discover()
        self.assertEqual(result.focused_window_id, "0xabc")
        self.assertEqual(result.windows[0].process_id, 123)
        self.assertEqual(result.issues, ())
        self.assertTrue(discovery.monitors()[0].focused)

    def test_hyprland_discovery_degrades_outside_hyprland(self):
        result = HyprlandWindowDiscovery(
            HyprlandWindowSettings("wayland", False), Runner(),
        ).discover()
        self.assertEqual(result.windows, ())
        self.assertEqual(result.issues[0].code, "linux.hyprland.unavailable")


if __name__ == "__main__":
    unittest.main()
