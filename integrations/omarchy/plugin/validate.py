#!/usr/bin/env python3
"""Repository-local contract gate for the independent Omarchy plugin."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def main() -> int:
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schemaVersion"] == 1
    assert manifest["id"] == "fam.os" and not manifest["id"].startswith("omarchy.")
    assert manifest["name"] == "FAM"
    assert manifest["version"] == "0.1.1"
    assert manifest["author"] == "FAM OS"
    assert manifest["kinds"] == ["bar-widget"]
    assert manifest["entryPoints"] == {"barWidget": "Widget.qml"}
    assert not any(path.is_symlink() for path in ROOT.rglob("*"))
    for entry in manifest["entryPoints"].values():
        assert (ROOT / entry).is_file()
    widget = (ROOT / "Widget.qml").read_text(encoding="utf-8")
    panel = (ROOT / "Panel.qml").read_text(encoding="utf-8")
    assert "BarWidget {" in widget
    assert 'source: Qt.resolvedUrl("Panel.qml")' in widget
    assert "Panel {" in panel and "KeyboardPanel {" in panel
    assert "PanelWindow" not in widget and "PanelWindow" not in panel
    assert manifest["barWidget"]["aliases"] == ["fam", "fam-goals"]
    transport = (ROOT / "FamService.qml").read_text(encoding="utf-8")
    assert "import QtWebSockets" in transport
    assert "/api/v1/events?token=" in transport
    assert "reconnectDelayMs" in transport and "Math.min(30000" in transport
    assert "65536" in transport
    assert '"curl", "-N' not in transport and "text/event-stream" not in transport
    assert "writeText" not in transport and "append" not in transport
    print("fam.os Omarchy plugin contract: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
