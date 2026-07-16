import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from fam_os.adapters.linux.application_discovery import LinuxApplicationDiscovery
from fam_os.adapters.linux.desktop_entries import (
    DesktopApplicationResult, DesktopEntryDiscovery, DesktopEntrySettings, parse_exec,
)
from fam_os.adapters.linux.processes import (
    LinuxProcessDiscovery, LinuxProcessDiscoverySettings, ProcessDiscoveryResult,
    parse_process_stat, parse_process_user_id,
)
from fam_os.adapters.linux.x11_windows import (
    WindowDiscoveryResult, X11WindowDiscovery, X11WindowSettings,
    parse_x11_root, parse_x11_window,
)
from fam_os.applications import (
    ApplicationIdentity, ApplicationLaunchSpec, ApplicationProcess,
    ApplicationWindow, DiscoveredApplication,
)


NOW = datetime(2026, 7, 16, 18, 0, tzinfo=timezone.utc)


class LinuxProcessDiscoveryTests(unittest.TestCase):
    def test_proc_stat_and_status_handle_spaced_command(self):
        fields = ["S", "7"] + ["0"] * 17 + ["12345"]
        parsed = parse_process_stat(f"42 (code helper) {' '.join(fields)}")
        self.assertEqual((42, "code helper", 7, 12345), parsed)
        self.assertEqual(1000, parse_process_user_id("Name:\tcode\nUid:\t1000 1000 1000 1000\n"))

    def test_current_user_processes_are_read_without_command_arguments(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _proc_entry(root, 42, os.getuid(), "code helper", 7, 12345)
            _proc_entry(root, 43, os.getuid() + 1, "foreign", 1, 1)
            result = LinuxProcessDiscovery(LinuxProcessDiscoverySettings(
                root, os.getuid(), 10
            )).discover()
        self.assertEqual(1, len(result.processes))
        self.assertEqual("true", result.processes[0].executable_name)
        self.assertEqual("code helper", result.processes[0].command_name)

    def test_missing_procfs_reports_safe_degradation(self):
        result = LinuxProcessDiscovery(LinuxProcessDiscoverySettings(
            Path("/path/that/does/not/exist"), os.getuid(), 10
        )).discover()
        self.assertEqual("linux.procfs.unavailable", result.issues[0].code)


class DesktopEntryDiscoveryTests(unittest.TestCase):
    def test_exec_parser_removes_field_codes_and_marks_shell_wrappers(self):
        launch = parse_exec("code --reuse-window %F")
        self.assertEqual(("--reuse-window",), launch.arguments)
        self.assertTrue(launch.accepts_files)
        self.assertTrue(launch.safe_without_shell)
        self.assertFalse(parse_exec("sh -c 'run thing'").safe_without_shell)
        self.assertIsNone(parse_exec("code --file=%f"))
        self.assertIsNone(parse_exec("%f --unsafe"))

    def test_desktop_precedence_visibility_and_launch_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            user = Path(directory) / "user"
            system = Path(directory) / "system"
            user.mkdir()
            system.mkdir()
            _desktop(user / "code.desktop", "User Code", "code %F", "Code")
            _desktop(system / "code.desktop", "System Code", "other")
            _desktop(system / "hidden.desktop", "Hidden", "hidden", hidden=True)
            result = DesktopEntryDiscovery(DesktopEntrySettings((user, system))).discover()
        self.assertEqual(1, len(result.applications))
        self.assertEqual("User Code", result.applications[0].identity.display_name)
        self.assertEqual("Code", result.applications[0].startup_window_class)


class X11WindowDiscoveryTests(unittest.TestCase):
    ROOT = (
        "_NET_CLIENT_LIST_STACKING(WINDOW): window id # 0x100001, 0x200002\n"
        "_NET_ACTIVE_WINDOW(WINDOW): window id # 0x200002\n"
    )

    def test_xprop_parsers_and_privacy_default(self):
        self.assertEqual((("0x100001", "0x200002"), "0x200002"), parse_x11_root(self.ROOT))
        details = (
            '_NET_WM_PID(CARDINAL) = 123\nWM_CLASS(STRING) = "code", "Code"\n'
            '_NET_WM_NAME(UTF8_STRING) = "private.py - project"\n'
        )
        window = parse_x11_window("0x200002", details)
        self.assertEqual(123, window.process_id)
        self.assertEqual("Code", window.application_class)
        self.assertIsNone(window.title)
        self.assertEqual("private.py - project", parse_x11_window(
            "0x200002", details, include_title=True
        ).title)

    def test_shell_free_probe_and_wayland_degradation(self):
        runner = Runner({
            ("xprop", "-root", "_NET_CLIENT_LIST_STACKING", "_NET_ACTIVE_WINDOW"): self.ROOT,
            ("xprop", "-id", "0x100001", "_NET_WM_PID", "WM_CLASS", "_NET_WM_NAME"):
                '_NET_WM_PID(CARDINAL) = 100\nWM_CLASS(STRING) = "code", "Code"',
            ("xprop", "-id", "0x200002", "_NET_WM_PID", "WM_CLASS", "_NET_WM_NAME"):
                '_NET_WM_PID(CARDINAL) = 200\nWM_CLASS(STRING) = "chrome", "Google-chrome"',
        })
        result = X11WindowDiscovery(X11WindowSettings("x11", True), runner).discover()
        self.assertEqual(2, len(result.windows))
        self.assertEqual("0x200002", result.focused_window_id)
        self.assertTrue(all(isinstance(item, tuple) for item in runner.commands))

        unavailable = X11WindowDiscovery(
            X11WindowSettings("wayland", False), runner
        ).discover()
        self.assertEqual("linux.window_discovery.unavailable", unavailable.issues[0].code)


class LinuxApplicationCompositionTests(unittest.TestCase):
    def test_correlates_process_and_window_without_titles(self):
        application = DiscoveredApplication(
            "code", ApplicationIdentity("linux.desktop.code", "Code"),
            ApplicationLaunchSpec("/usr/bin/code"), "Code",
        )
        process = ApplicationProcess(42, 1, 1000, "code", "code", 10)
        window = ApplicationWindow("0x42", 42, "Code")
        discovery = LinuxApplicationDiscovery(
            Provider(DesktopApplicationResult((application,))),
            Provider(ProcessDiscoveryResult((process,))),
            Provider(WindowDiscoveryResult((window,), "0x42")),
            clock=lambda: NOW,
        )
        snapshot = discovery.collect()
        self.assertEqual("linux.desktop.code", snapshot.processes[0].application_id)
        self.assertEqual("linux.desktop.code", snapshot.windows[0].application_id)
        self.assertEqual("0x42", snapshot.focused_window_id)


class Provider:
    def __init__(self, value):
        self.value = value

    def discover(self):
        return self.value


class Runner:
    def __init__(self, outputs):
        self.outputs = outputs
        self.commands = []

    def run(self, command, timeout_seconds=10.0):
        self.commands.append(command)
        return self.outputs.get(command)


def _proc_entry(root, pid, uid, command, parent, start):
    directory = root / str(pid)
    directory.mkdir()
    (directory / "status").write_text(f"Uid:\t{uid} {uid} {uid} {uid}\n")
    fields = ["S", str(parent)] + ["0"] * 17 + [str(start)]
    (directory / "stat").write_text(f"{pid} ({command}) {' '.join(fields)}")
    (directory / "exe").symlink_to("/usr/bin/true")


def _desktop(path, name, executable, window_class=None, hidden=False):
    lines = ["[Desktop Entry]", "Type=Application", f"Name={name}", f"Exec={executable}"]
    if window_class:
        lines.append(f"StartupWMClass={window_class}")
    if hidden:
        lines.append("Hidden=true")
    path.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    unittest.main()
