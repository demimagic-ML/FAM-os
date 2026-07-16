"""Read-only freedesktop desktop-entry and safe launch metadata discovery."""

import configparser
import hashlib
import re
import shlex
from dataclasses import dataclass
from pathlib import Path

from fam_os.applications import (
    ApplicationDiscoveryIssue, ApplicationIdentity, ApplicationLaunchSpec,
    DiscoveredApplication, DiscoverySurface,
)


_SHELLS = {"sh", "bash", "dash", "zsh", "fish", "csh", "tcsh"}
_FIELD_CODES = {"%f", "%F", "%u", "%U", "%i", "%c", "%k"}


@dataclass(frozen=True, slots=True)
class DesktopApplicationResult:
    applications: tuple[DiscoveredApplication, ...]
    issues: tuple[ApplicationDiscoveryIssue, ...] = ()


@dataclass(frozen=True, slots=True)
class DesktopEntrySettings:
    application_directories: tuple[Path, ...]
    include_no_display: bool = False
    maximum_entries: int = 4096

    def __post_init__(self) -> None:
        if self.maximum_entries <= 0 or len(set(self.application_directories)) != len(
            self.application_directories
        ):
            raise ValueError("desktop entry settings are invalid")


class DesktopEntryDiscovery:
    def __init__(self, settings: DesktopEntrySettings):
        self._settings = settings

    def discover(self) -> DesktopApplicationResult:
        applications = {}
        issues = []
        for directory in self._settings.application_directories:
            for path in _desktop_files(directory):
                entry_id = _entry_id(path.name)
                if entry_id in applications:
                    continue
                application = parse_desktop_entry(
                    path, entry_id, self._settings.include_no_display
                )
                if application is not None:
                    applications[entry_id] = application
                if len(applications) >= self._settings.maximum_entries:
                    issues.append(_issue("linux.desktop_entry.limit"))
                    return DesktopApplicationResult(_sorted(applications), tuple(issues))
        return DesktopApplicationResult(_sorted(applications), tuple(issues))


def parse_desktop_entry(path: Path, entry_id: str, include_no_display=False):
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.optionxform = str
    try:
        with path.open("r", encoding="utf-8", errors="strict") as stream:
            parser.read_file(stream)
        values = parser["Desktop Entry"]
    except (OSError, UnicodeError, configparser.Error, KeyError):
        return None
    if values.get("Type") != "Application" or _truthy(values.get("Hidden")):
        return None
    if _truthy(values.get("NoDisplay")) and not include_no_display:
        return None
    name = values.get("Name", "").strip()
    launch = parse_exec(values.get("Exec", ""), _truthy(values.get("Terminal")))
    if not name or launch is None:
        return None
    identity = ApplicationIdentity(_application_id(entry_id), name)
    window_class = values.get("StartupWMClass") or None
    return DiscoveredApplication(entry_id, identity, launch, window_class)


def parse_exec(value: str, terminal=False) -> ApplicationLaunchSpec | None:
    if not value.strip() or "\0" in value or "\n" in value:
        return None
    try:
        tokens = shlex.split(value, posix=True)
    except ValueError:
        return None
    if not tokens:
        return None
    arguments = []
    accepts_files = any(token in {"%f", "%F"} for token in tokens)
    accepts_uris = any(token in {"%u", "%U"} for token in tokens)
    for token in tokens[1:]:
        if token in _FIELD_CODES:
            continue
        normalized = token.replace("%%", "%")
        if re.search(r"%[A-Za-z]", normalized):
            return None
        arguments.append(normalized)
    executable = tokens[0].replace("%%", "%")
    if re.search(r"%[A-Za-z]", executable):
        return None
    safe = Path(executable).name not in _SHELLS
    return ApplicationLaunchSpec(
        executable, tuple(arguments), accepts_files, accepts_uris, terminal, safe
    )


def _desktop_files(directory):
    try:
        return tuple(sorted(directory.glob("*.desktop")))
    except OSError:
        return ()


def _entry_id(filename):
    value = filename.removesuffix(".desktop")
    normalized = re.sub(r"[^A-Za-z0-9._:-]", "_", value)[:128]
    return normalized or hashlib.sha256(filename.encode()).hexdigest()[:20]


def _application_id(entry_id):
    digest = hashlib.sha256(entry_id.encode()).hexdigest()[:20]
    return f"linux.desktop.{digest}"


def _truthy(value):
    return str(value).strip().lower() == "true"


def _sorted(applications):
    return tuple(sorted(applications.values(), key=lambda item: item.desktop_entry_id))


def _issue(code):
    return ApplicationDiscoveryIssue(
        DiscoverySurface.APPLICATIONS, code,
        "Installed application discovery reached its configured limit.",
    )
