"""Read-only X11 EWMH window and focus discovery through shell-free xprop."""

import ast
import re
from dataclasses import dataclass

from fam_os.adapters.linux.command import CommandRunner, SubprocessCommandRunner
from fam_os.applications import (
    ApplicationDiscoveryIssue, ApplicationWindow, DiscoverySurface,
)


_WINDOW_ID = re.compile(r"0x[0-9a-fA-F]+")


@dataclass(frozen=True, slots=True)
class WindowDiscoveryResult:
    windows: tuple[ApplicationWindow, ...]
    focused_window_id: str | None
    issues: tuple[ApplicationDiscoveryIssue, ...] = ()


@dataclass(frozen=True, slots=True)
class X11WindowSettings:
    session_type: str
    display_available: bool
    include_titles: bool = False
    maximum_windows: int = 256

    def __post_init__(self) -> None:
        if self.maximum_windows <= 0:
            raise ValueError("X11 maximum windows must be positive")


class X11WindowDiscovery:
    def __init__(
        self, settings: X11WindowSettings,
        runner: CommandRunner | None = None,
    ):
        self._settings = settings
        self._runner = runner or SubprocessCommandRunner()

    def discover(self) -> WindowDiscoveryResult:
        if self._settings.session_type.lower() != "x11" or not self._settings.display_available:
            return WindowDiscoveryResult((), None, (_unavailable(),))
        root = self._runner.run((
            "xprop", "-root", "_NET_CLIENT_LIST_STACKING", "_NET_ACTIVE_WINDOW",
        ))
        if root is None:
            return WindowDiscoveryResult((), None, (_unavailable(),))
        window_ids, focused = parse_x11_root(root)
        issues = []
        if len(window_ids) > self._settings.maximum_windows:
            window_ids = window_ids[:self._settings.maximum_windows]
            issues.append(ApplicationDiscoveryIssue(
                DiscoverySurface.WINDOWS, "linux.x11.window_limit",
                "Window discovery reached its configured limit.",
            ))
        windows = tuple(
            window for window_id in window_ids
            if (window := self._window(window_id)) is not None
        )
        if focused not in {item.window_id for item in windows}:
            focused = None
        return WindowDiscoveryResult(windows, focused, tuple(issues))

    def _window(self, window_id):
        output = self._runner.run((
            "xprop", "-id", window_id, "_NET_WM_PID", "WM_CLASS", "_NET_WM_NAME",
        ))
        if output is None:
            return None
        return parse_x11_window(window_id, output, self._settings.include_titles)


def parse_x11_root(content: str) -> tuple[tuple[str, ...], str | None]:
    window_ids = ()
    focused = None
    for line in content.splitlines():
        values = tuple(item.lower() for item in _WINDOW_ID.findall(line))
        if line.startswith("_NET_CLIENT_LIST"):
            window_ids = values
        elif line.startswith("_NET_ACTIVE_WINDOW") and values and values[0] != "0x0":
            focused = values[0]
    return tuple(dict.fromkeys(window_ids)), focused


def parse_x11_window(window_id: str, content: str, include_title=False):
    process_id = None
    application_class = None
    title = None
    for line in content.splitlines():
        if line.startswith("_NET_WM_PID"):
            process_id = _integer_value(line)
        elif line.startswith("WM_CLASS"):
            values = _quoted_values(line)
            application_class = values[-1] if values else None
        elif include_title and line.startswith("_NET_WM_NAME"):
            values = _quoted_values(line)
            title = values[0][:1024] if values else None
    try:
        return ApplicationWindow(
            window_id.lower(), process_id, application_class, title
        )
    except ValueError:
        return None


def _integer_value(line):
    match = re.search(r"=\s*(\d+)", line)
    return int(match.group(1)) if match else None


def _quoted_values(line):
    _, _, value = line.partition("=")
    values = []
    for candidate in re.findall(r'"(?:[^"\\]|\\.)*"', value):
        try:
            decoded = ast.literal_eval(candidate)
        except (ValueError, SyntaxError):
            continue
        if isinstance(decoded, str) and decoded.strip():
            values.append(decoded.strip())
    return tuple(values)


def _unavailable():
    return ApplicationDiscoveryIssue(
        DiscoverySurface.WINDOWS, "linux.window_discovery.unavailable",
        "Window and focus discovery is unavailable for this desktop session.",
    )
