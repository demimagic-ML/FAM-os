"""Central, structured Omarchy host capability detection."""

from __future__ import annotations

import os
import platform
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Mapping

from fam_os.adapters.linux.command import SubprocessCommandRunner
from fam_os.adapters.omarchy.agent_discovery import (
    AgentCapability, InferenceEndpoint, browser_capabilities, discover_agents,
    discover_inference_endpoints,
)
from fam_os.adapters.omarchy.environment import OmarchyPaths, omarchy_paths
from fam_os.adapters.omarchy.session import detect_session


@dataclass(frozen=True, slots=True)
class HostCapability:
    distribution: str
    distribution_like: tuple[str, ...]
    version: str | None
    channel: str | None
    architecture: str
    omarchy: bool
    support_level: str
    supported: bool


@dataclass(frozen=True, slots=True)
class DesktopCapability:
    session: str
    desktops: tuple[str, ...]
    compositor: str | None
    manager: str | None
    shell: str | None
    graphical: bool


@dataclass(frozen=True, slots=True)
class FeatureCapability:
    window_observation: bool
    application_launch: bool
    screen_capture: bool
    browser_testing: bool
    controlled_input: bool
    system_snapshots: bool
    quickshell_plugins: bool


@dataclass(frozen=True, slots=True)
class OmarchyCapabilities:
    host: HostCapability
    desktop: DesktopCapability
    features: FeatureCapability
    agents: tuple[AgentCapability, ...]
    inference: tuple[InferenceEndpoint, ...]
    browsers: tuple[AgentCapability, ...]
    paths: OmarchyPaths
    issues: tuple[str, ...]

    def document(self) -> dict[str, object]:
        return asdict(self)


class OmarchyDetector:
    def __init__(
        self,
        *,
        environment: Mapping[str, str] | None = None,
        home: Path | None = None,
        os_release: Path = Path("/etc/os-release"),
        runner=None,
        which: Callable[[str], str | None] = shutil.which,
        architecture: Callable[[], str] = platform.machine,
        endpoint_discovery=discover_inference_endpoints,
    ) -> None:
        self.environment = dict(os.environ if environment is None else environment)
        self.paths = omarchy_paths(self.environment, home=home)
        self.os_release = os_release
        self.runner = runner or SubprocessCommandRunner()
        self.which = which
        self.architecture = architecture
        self.endpoint_discovery = endpoint_discovery

    def detect(self) -> OmarchyCapabilities:
        release = _read_os_release(self.os_release)
        session = detect_session(self.environment)
        version = _read_text(self.paths.version_file)
        channel = self.runner.run(("omarchy-version-channel",))
        omarchy = _is_omarchy(release, self.paths, self.which)
        architecture = self.architecture()
        support_level = _support_level(omarchy, version, architecture)
        compositor = "hyprland" if session.is_hyprland else None
        manager = "uwsm" if self.which("uwsm-app") or self.which("uwsm") else None
        shell = "quickshell" if self.which("quickshell") else None
        agents = discover_agents(self.which, _read_text(
            self.paths.config_home / "omarchy/defaults/agent",
        ))
        browsers = browser_capabilities(self.which)
        capture = any(self.which(item) for item in (
            "omarchy-capture-screenshot", "grim", "gnome-screenshot",
        ))
        controlled_input = any(self.which(item) for item in ("wtype", "ydotool"))
        snapshots = self.which("omarchy-snapshot") is not None
        plugin_support = bool(
            omarchy and shell and self.which("omarchy-shell")
        )
        issues = []
        if not omarchy:
            issues.append("host.omarchy.not_detected")
        elif support_level == "unsupported":
            issues.append("host.omarchy.unsupported_version_or_architecture")
        elif support_level == "experimental":
            issues.append("host.omarchy.experimental_aarch64")
        if session.session_type == "wayland" and compositor is None:
            issues.append("desktop.wayland.generic")
        if not browsers:
            issues.append("application.browser.unavailable")
        return OmarchyCapabilities(
            host=HostCapability(
                release.get("ID", "unknown"),
                tuple(release.get("ID_LIKE", "").split()),
                version, channel, architecture, omarchy, support_level,
                support_level == "supported",
            ),
            desktop=DesktopCapability(
                session.session_type, session.desktop, compositor, manager, shell,
                session.graphical,
            ),
            features=FeatureCapability(
                window_observation=session.is_hyprland or session.session_type == "x11",
                application_launch=manager is not None,
                screen_capture=capture,
                browser_testing=bool(browsers),
                controlled_input=controlled_input,
                system_snapshots=snapshots,
                quickshell_plugins=plugin_support,
            ),
            agents=agents,
            inference=self.endpoint_discovery(),
            browsers=browsers,
            paths=self.paths,
            issues=tuple(issues),
        )


def _read_os_release(path: Path) -> dict[str, str]:
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    values = {}
    for line in content.splitlines():
        key, separator, raw = line.partition("=")
        if separator and key:
            values[key] = raw.strip().strip('"').strip("'")
    return values


def _read_text(path: Path) -> str | None:
    try:
        value = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return value or None


def _is_omarchy(
    release: Mapping[str, str], paths: OmarchyPaths,
    which: Callable[[str], str | None],
) -> bool:
    identifiers = {release.get("ID", "").casefold()}
    identifiers.update(release.get("ID_LIKE", "").casefold().split())
    return (
        "omarchy" in identifiers
        or paths.version_file.is_file()
        or which("omarchy") is not None
    )


def _support_level(omarchy: bool, version: str | None, architecture: str) -> str:
    if not omarchy:
        return "not-omarchy"
    try:
        major = int(str(version).split(".", 1)[0])
    except (TypeError, ValueError):
        return "unsupported"
    if major != 4:
        return "unsupported"
    if architecture == "x86_64":
        return "supported"
    if architecture == "aarch64":
        return "experimental"
    return "unsupported"
