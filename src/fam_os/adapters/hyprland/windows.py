"""Read-only Hyprland window, focus, workspace, and monitor discovery."""

from __future__ import annotations

import json
from dataclasses import dataclass

from fam_os.adapters.linux.command import CommandRunner, SubprocessCommandRunner
from fam_os.adapters.linux.x11_windows import WindowDiscoveryResult
from fam_os.applications import (
    ApplicationDiscoveryIssue, ApplicationWindow, DiscoverySurface,
)


@dataclass(frozen=True, slots=True)
class HyprlandWindowSettings:
    session_type: str
    signature_available: bool
    include_titles: bool = False
    maximum_windows: int = 256

    def __post_init__(self) -> None:
        if self.maximum_windows <= 0:
            raise ValueError("Hyprland maximum windows must be positive")


@dataclass(frozen=True, slots=True)
class HyprlandMonitor:
    monitor_id: int
    name: str
    x: int
    y: int
    width: int
    height: int
    scale: float
    focused: bool


class HyprlandWindowDiscovery:
    def __init__(
        self, settings: HyprlandWindowSettings,
        runner: CommandRunner | None = None,
    ) -> None:
        self._settings = settings
        self._runner = runner or SubprocessCommandRunner()

    def discover(self) -> WindowDiscoveryResult:
        if (
            self._settings.session_type.casefold() != "wayland"
            or not self._settings.signature_available
        ):
            return WindowDiscoveryResult((), None, (_unavailable(),))
        clients = self._runner.run(("hyprctl", "-j", "clients"))
        active = self._runner.run(("hyprctl", "-j", "activewindow"))
        if clients is None or active is None:
            return WindowDiscoveryResult((), None, (_unavailable(),))
        try:
            windows = parse_clients(clients, include_titles=self._settings.include_titles)
            focused = parse_active_window(active)
        except (TypeError, ValueError, json.JSONDecodeError):
            return WindowDiscoveryResult((), None, (
                ApplicationDiscoveryIssue(
                    DiscoverySurface.WINDOWS, "linux.hyprland.invalid_response",
                    "Hyprland returned invalid window information.",
                ),
            ))
        issues = []
        if len(windows) > self._settings.maximum_windows:
            windows = windows[:self._settings.maximum_windows]
            issues.append(ApplicationDiscoveryIssue(
                DiscoverySurface.WINDOWS, "linux.hyprland.window_limit",
                "Window discovery reached its configured limit.",
            ))
        identifiers = {item.window_id for item in windows}
        return WindowDiscoveryResult(
            windows, focused if focused in identifiers else None, tuple(issues),
        )

    def monitors(self) -> tuple[HyprlandMonitor, ...]:
        output = self._runner.run(("hyprctl", "-j", "monitors"))
        if output is None:
            return ()
        try:
            return parse_monitors(output)
        except (TypeError, ValueError, json.JSONDecodeError):
            return ()


def parse_clients(content: str, *, include_titles: bool = False) -> tuple[ApplicationWindow, ...]:
    value = json.loads(content)
    if not isinstance(value, list):
        raise ValueError("Hyprland clients response must be a list")
    windows = []
    for entry in value:
        if not isinstance(entry, dict) or entry.get("mapped") is False or entry.get("hidden") is True:
            continue
        address = _address(entry.get("address"))
        if address is None:
            continue
        process_id = entry.get("pid")
        if not isinstance(process_id, int) or process_id <= 0:
            process_id = None
        application_class = entry.get("class") or entry.get("initialClass")
        if not isinstance(application_class, str) or not application_class.strip():
            application_class = None
        title = entry.get("title") if include_titles else None
        if not isinstance(title, str) or not title.strip():
            title = None
        windows.append(ApplicationWindow(
            address, process_id, application_class,
            title[:1024] if title is not None else None,
        ))
    return tuple(windows)


def parse_active_window(content: str) -> str | None:
    value = json.loads(content)
    if not isinstance(value, dict):
        raise ValueError("Hyprland active-window response must be an object")
    return _address(value.get("address"))


def parse_monitors(content: str) -> tuple[HyprlandMonitor, ...]:
    value = json.loads(content)
    if not isinstance(value, list):
        raise ValueError("Hyprland monitors response must be a list")
    monitors = []
    for entry in value:
        if not isinstance(entry, dict):
            continue
        values = tuple(entry.get(key) for key in ("id", "x", "y", "width", "height"))
        if not all(isinstance(item, int) for item in values):
            continue
        name = entry.get("name")
        scale = entry.get("scale", 1.0)
        if not isinstance(name, str) or not isinstance(scale, (int, float)):
            continue
        monitors.append(HyprlandMonitor(
            values[0], name, values[1], values[2], values[3], values[4],
            float(scale), bool(entry.get("focused")),
        ))
    return tuple(monitors)


def _address(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.casefold()
    if normalized.startswith("0x"):
        normalized = normalized[2:]
    if not normalized or any(character not in "0123456789abcdef" for character in normalized):
        return None
    return "0x" + normalized


def _unavailable() -> ApplicationDiscoveryIssue:
    return ApplicationDiscoveryIssue(
        DiscoverySurface.WINDOWS, "linux.hyprland.unavailable",
        "Hyprland window and focus discovery is unavailable.",
    )
