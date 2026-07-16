"""Explicit XDG environment translation for Linux application discovery."""

from pathlib import Path

from fam_os.adapters.linux.application_discovery import (
    LinuxApplicationDiscoverySettings,
)


def application_discovery_settings(environment, home: Path):
    data_home = Path(environment.get("XDG_DATA_HOME", home / ".local/share"))
    raw_data_dirs = environment.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share")
    data_dirs = tuple(Path(item) for item in raw_data_dirs.split(":") if item)
    directories = tuple(dict.fromkeys(
        (data_home / "applications",) + tuple(path / "applications" for path in data_dirs)
    ))
    return LinuxApplicationDiscoverySettings(
        directories,
        environment.get("XDG_SESSION_TYPE", "unknown"),
        bool(environment.get("DISPLAY")),
    )
