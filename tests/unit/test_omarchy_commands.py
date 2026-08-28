import unittest

from fam_os.adapters.omarchy.commands import uwsm_application_command
from fam_os.adapters.omarchy.session import detect_session


class OmarchyCommandTests(unittest.TestCase):
    def test_builds_shell_free_uwsm_app_command(self):
        self.assertEqual(uwsm_application_command(
            ("chromium", "--app=http://127.0.0.1:8765"),
            executable="/usr/bin/uwsm-app",
        ), (
            "/usr/bin/uwsm-app", "--", "chromium", "--app=http://127.0.0.1:8765",
        ))

    def test_builds_full_uwsm_command_when_fast_client_is_not_selected(self):
        self.assertEqual(uwsm_application_command(
            ("org.example.App.desktop",), executable="/usr/bin/uwsm",
        ), ("/usr/bin/uwsm", "app", "--", "org.example.App.desktop"))

    def test_rejects_empty_application_commands(self):
        with self.assertRaises(ValueError):
            uwsm_application_command((), executable="/usr/bin/uwsm-app")

    def test_detects_hyprland_session_from_desktop_or_signature(self):
        session = detect_session({
            "XDG_SESSION_TYPE": "wayland", "XDG_CURRENT_DESKTOP": "Hyprland:Omarchy",
            "WAYLAND_DISPLAY": "wayland-1",
        })
        self.assertTrue(session.graphical)
        self.assertTrue(session.is_hyprland)


if __name__ == "__main__":
    unittest.main()
