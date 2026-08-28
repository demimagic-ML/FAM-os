"""XDG-correct Omarchy filesystem and session locations."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True, slots=True)
class OmarchyPaths:
    home: Path
    data_home: Path
    config_home: Path
    cache_home: Path
    state_home: Path
    runtime_dir: Path
    omarchy_root: Path

    @property
    def version_file(self) -> Path:
        return self.omarchy_root / "version"

    @property
    def plugin_root(self) -> Path:
        return self.config_home / "omarchy/plugins"

    @property
    def usage_root(self) -> Path:
        return self.state_home / "omarchy/agents/usage"

    @property
    def fam_state_root(self) -> Path:
        return self.data_home / "fam-os"

    @property
    def fam_runtime_root(self) -> Path:
        return self.runtime_dir / "fam-os"


def omarchy_paths(
    environment: Mapping[str, str] | None = None,
    *,
    home: Path | None = None,
    uid: int | None = None,
) -> OmarchyPaths:
    values = os.environ if environment is None else environment
    owner_home = (home or Path(values.get("HOME", Path.home()))).expanduser()
    effective_uid = os.geteuid() if uid is None else uid
    return OmarchyPaths(
        home=owner_home,
        data_home=Path(values.get("XDG_DATA_HOME", owner_home / ".local/share")),
        config_home=Path(values.get("XDG_CONFIG_HOME", owner_home / ".config")),
        cache_home=Path(values.get("XDG_CACHE_HOME", owner_home / ".cache")),
        state_home=Path(values.get("XDG_STATE_HOME", owner_home / ".local/state")),
        runtime_dir=Path(values.get("XDG_RUNTIME_DIR", f"/run/user/{effective_uid}")),
        omarchy_root=Path(values.get("OMARCHY_PATH", "/usr/share/omarchy")),
    )
