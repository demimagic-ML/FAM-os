"""Provider-neutral installed application, process, window, and launch discovery."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from fam_os.applications.identifiers import require_identifier, require_text
from fam_os.applications.identity import ApplicationIdentity


class DiscoverySurface(StrEnum):
    APPLICATIONS = "applications"
    PROCESSES = "processes"
    WINDOWS = "windows"
    FOCUS = "focus"
    LAUNCH = "launch"


@dataclass(frozen=True, slots=True)
class ApplicationDiscoveryIssue:
    surface: DiscoverySurface
    code: str
    safe_message: str

    def __post_init__(self) -> None:
        require_identifier(self.code, "discovery issue code")
        require_text(self.safe_message, "discovery issue message")


@dataclass(frozen=True, slots=True)
class ApplicationLaunchSpec:
    executable: str
    arguments: tuple[str, ...] = ()
    accepts_files: bool = False
    accepts_uris: bool = False
    terminal: bool = False
    safe_without_shell: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "executable", require_text(self.executable, "executable"))
        if any(not isinstance(item, str) or "\0" in item for item in self.arguments):
            raise ValueError("launch arguments must be null-free strings")


@dataclass(frozen=True, slots=True)
class DiscoveredApplication:
    desktop_entry_id: str
    identity: ApplicationIdentity
    launch: ApplicationLaunchSpec
    startup_window_class: str | None = None

    def __post_init__(self) -> None:
        require_identifier(self.desktop_entry_id, "desktop_entry_id")
        if self.startup_window_class is not None:
            object.__setattr__(
                self, "startup_window_class",
                require_text(self.startup_window_class, "startup_window_class"),
            )


@dataclass(frozen=True, slots=True)
class ApplicationProcess:
    process_id: int
    parent_process_id: int
    user_id: int
    executable_name: str
    command_name: str
    start_time_ticks: int
    application_id: str | None = None

    def __post_init__(self) -> None:
        if min(self.process_id, self.parent_process_id, self.user_id, self.start_time_ticks) < 0:
            raise ValueError("process numeric fields cannot be negative")
        require_text(self.executable_name, "executable_name")
        require_text(self.command_name, "command_name")
        if self.application_id is not None:
            require_identifier(self.application_id, "application_id")


@dataclass(frozen=True, slots=True)
class ApplicationWindow:
    window_id: str
    process_id: int | None
    application_class: str | None
    title: str | None = None
    application_id: str | None = None

    def __post_init__(self) -> None:
        require_identifier(self.window_id, "window_id")
        if self.process_id is not None and self.process_id <= 0:
            raise ValueError("window process_id must be positive")
        for name in ("application_class", "title"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, require_text(value, name))
        if self.application_id is not None:
            require_identifier(self.application_id, "application_id")


@dataclass(frozen=True, slots=True)
class ApplicationDiscoverySnapshot:
    captured_at: datetime
    applications: tuple[DiscoveredApplication, ...]
    processes: tuple[ApplicationProcess, ...]
    windows: tuple[ApplicationWindow, ...]
    focused_window_id: str | None
    issues: tuple[ApplicationDiscoveryIssue, ...] = ()

    def __post_init__(self) -> None:
        if self.captured_at.tzinfo is None:
            raise ValueError("application discovery time must be timezone-aware")
        if self.focused_window_id is not None:
            require_identifier(self.focused_window_id, "focused_window_id")
            if self.focused_window_id not in {item.window_id for item in self.windows}:
                raise ValueError("focused window must exist in the window snapshot")
        _unique(self.applications, lambda item: item.desktop_entry_id, "desktop entries")
        _unique(self.processes, lambda item: item.process_id, "process IDs")
        _unique(self.windows, lambda item: item.window_id, "window IDs")


def _unique(items, key, name):
    values = tuple(key(item) for item in items)
    if len(set(values)) != len(values):
        raise ValueError(f"discovered {name} must be unique")
