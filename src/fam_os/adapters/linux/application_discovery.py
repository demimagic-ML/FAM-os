"""Correlation and snapshot composition for read-only Linux application discovery."""

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path

from fam_os.adapters.linux.desktop_entries import (
    DesktopEntryDiscovery, DesktopEntrySettings,
)
from fam_os.adapters.linux.processes import LinuxProcessDiscovery
from fam_os.adapters.linux.x11_windows import X11WindowDiscovery, X11WindowSettings
from fam_os.applications import ApplicationDiscoverySnapshot


def _utc_now():
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class LinuxApplicationDiscoverySettings:
    application_directories: tuple[Path, ...]
    session_type: str
    display_available: bool
    include_window_titles: bool = False


class LinuxApplicationDiscovery:
    def __init__(
        self, applications, processes, windows,
        clock: Callable[[], datetime] = _utc_now,
    ):
        self._applications = applications
        self._processes = processes
        self._windows = windows
        self._clock = clock

    @classmethod
    def standard(cls, settings: LinuxApplicationDiscoverySettings, runner=None):
        applications = DesktopEntryDiscovery(DesktopEntrySettings(
            settings.application_directories
        ))
        processes = LinuxProcessDiscovery()
        windows = X11WindowDiscovery(X11WindowSettings(
            settings.session_type, settings.display_available,
            settings.include_window_titles,
        ), runner)
        return cls(applications, processes, windows)

    def collect(self) -> ApplicationDiscoverySnapshot:
        applications = self._applications.discover()
        processes = self._processes.discover()
        windows = self._windows.discover()
        correlated_processes = _correlate_processes(
            processes.processes, applications.applications
        )
        correlated_windows = _correlate_windows(
            windows.windows, correlated_processes, applications.applications
        )
        return ApplicationDiscoverySnapshot(
            self._clock(), applications.applications, correlated_processes,
            correlated_windows, windows.focused_window_id,
            applications.issues + processes.issues + windows.issues,
        )


def _correlate_processes(processes, applications):
    executable_owners = {}
    for application in applications:
        name = Path(application.launch.executable).name.casefold()
        executable_owners.setdefault(name, []).append(application.identity.application_id)
    correlated = []
    for process in processes:
        owners = executable_owners.get(process.executable_name.casefold(), ())
        application_id = owners[0] if len(owners) == 1 else None
        correlated.append(replace(process, application_id=application_id))
    return tuple(correlated)


def _correlate_windows(windows, processes, applications):
    process_owners = {
        item.process_id: item.application_id for item in processes
        if item.application_id is not None
    }
    class_candidates = {}
    for application in applications:
        if application.startup_window_class is not None:
            key = application.startup_window_class.casefold()
            class_candidates.setdefault(key, []).append(
                application.identity.application_id
            )
    class_owners = {
        key: owners[0] for key, owners in class_candidates.items()
        if len(owners) == 1
    }
    correlated = []
    for window in windows:
        application_id = process_owners.get(window.process_id)
        if application_id is None and window.application_class is not None:
            application_id = class_owners.get(window.application_class.casefold())
        correlated.append(replace(window, application_id=application_id))
    return tuple(correlated)
