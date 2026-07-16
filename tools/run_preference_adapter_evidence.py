#!/usr/bin/env python3
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from fam_os.adaptation import (
    FilePreferenceStore, PreferenceKey, UserPreference, UserPreferenceProfile,
)


def main():
    root = Path(__file__).parents[1] / "artifacts/adaptation/phase11.3"
    root.mkdir(parents=True, exist_ok=True)
    path = root / "owner.preferences.json"
    now = datetime.now(UTC)
    store = FilePreferenceStore(path, "user.local")
    store.save(UserPreferenceProfile("user.local", (
        UserPreference(PreferenceKey.QUALITY_PRIORITY, .8, now),
        UserPreference(PreferenceKey.ENERGY_PRIORITY, .4, now),
    )))
    inspected = store.inspect("user.local")
    receipt = store.reset("user.local", now)
    (root / "preference-evidence.json").write_text(json.dumps({
        "inspected": asdict(inspected), "reset": asdict(receipt),
        "remaining_preferences": len(store.inspect("user.local").preferences),
        "file_mode": oct(path.stat().st_mode & 0o777),
    }, indent=2, sort_keys=True, default=str) + "\n")


if __name__ == "__main__":
    main()
