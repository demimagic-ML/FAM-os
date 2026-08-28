"""Static release checks for files consumed by Omarchy and Arch packaging."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    manifest = json.loads((ROOT / "integrations/omarchy/plugin/manifest.json").read_text())
    assert manifest["schemaVersion"] == 1
    assert manifest == {
        "schemaVersion": 1,
        "id": "fam.os",
        "name": "FAM",
        "version": "0.1.0",
        "author": "FAM OS",
        "license": "MIT",
        "description": "Goal progress and controls for FAM",
        "kinds": ["bar-widget", "panel"],
        "entryPoints": {"barWidget": "Widget.qml", "panel": "Panel.qml"},
        "barWidget": manifest["barWidget"],
    }
    assert manifest["entryPoints"]["barWidget"] == "Widget.qml"
    assert manifest["entryPoints"]["panel"] == "Panel.qml"
    plugin_root = ROOT / "integrations/omarchy/plugin"
    assert not any(path.is_symlink() for path in plugin_root.rglob("*"))
    panel = (plugin_root / "Panel.qml").read_text()
    assert "function open(payloadJson)" in panel
    assert "function close()" in panel
    widget = (plugin_root / "Widget.qml").read_text()
    assert '["omarchy-shell", "shell", "summon", "fam.os", "{}"]' in widget
    service = (plugin_root / "FamService.qml").read_text()
    assert "QtWebSockets" in service and "/api/v1/events?token=" in service
    assert "event-stream" not in service and '"curl", "-N' not in service
    for relative in (
        "integrations/omarchy/plugin/Widget.qml",
        "integrations/omarchy/plugin/Panel.qml",
        "integrations/omarchy/plugin/FamService.qml",
        "packaging/systemd/fam-os.service",
        "packaging/systemd/fam-os-desktop.service",
        "packaging/systemd/fam-os-usage.service",
        "packaging/systemd/fam-os-usage.timer",
        "packaging/arch/PKGBUILD",
        "packaging/arch/.SRCINFO",
        "packaging/arch/fam-os.install",
        "packaging/desktop/fam-os.desktop",
        "packaging/icons/fam-os.png",
        "packaging/keys/fam-os-release.asc",
        "packaging/keys/fam-os-release.fingerprint",
        "packaging/omarchy/support-matrix.json",
        "packaging/omarchy/omarchy-pkgs/fam-os/.omarchy/package.json",
        "packaging/omarchy/omarchy-pkgs/fam-os/.omarchy/upstream.sh",
        "packaging/omarchy/omarchy-pkgs/fam-os/PKGBUILD",
        "packaging/omarchy/omarchy-pkgs/fam-os/fam-os.install",
    ):
        path = ROOT / relative
        assert path.is_file() and path.stat().st_size > 0, relative
    for relative in (
        "integrations/omarchy/launcher/omarchy-fam",
        "integrations/omarchy/usage-collector/omarchy-agent-usage-fam",
        "packaging/omarchy/bootstrap.sh",
        "tools/omarchy/vm-e2e.sh",
        "tools/omarchy/release-package.sh",
        "tools/omarchy/source-archive.sh",
        "packaging/omarchy/sync-package-source.sh",
        "packaging/omarchy/omarchy-pkgs/fam-os/.omarchy/upstream.sh",
    ):
        path = ROOT / relative
        content = path.read_text()
        assert content.startswith("#!"), relative
        assert os.access(path, os.X_OK), f"not executable: {relative}"
        subprocess.run(("bash", "-n", str(path)), check=True)

    package = (ROOT / "packaging/arch/PKGBUILD").read_text()
    assert "arch=('x86_64' 'aarch64')" in package
    assert "releases/download/v$pkgver/$pkgname-$pkgver.tar.gz" in package
    assert "pip install" not in package and ".venv" not in package
    assert "python-playwright" in package and "chromium" in package
    assert "openai-codex:" in package
    assert "options=('docs')" in package
    assert "/omarchy/plugin/" not in package
    assert "packaging/keys/fam-os-release.asc" in package
    omarchy_package = (
        ROOT / "packaging/omarchy/omarchy-pkgs/fam-os/PKGBUILD"
    ).read_text()
    assert "arch=('x86_64')" in omarchy_package
    assert "aarch64" not in omarchy_package
    assert "options=('docs')" in omarchy_package
    assert "packaging/keys/fam-os-release.asc" in omarchy_package
    assert (ROOT / "packaging/arch/fam-os.install").read_text() == (
        ROOT / "packaging/omarchy/omarchy-pkgs/fam-os/fam-os.install"
    ).read_text()
    metadata = json.loads((
        ROOT / "packaging/omarchy/omarchy-pkgs/fam-os/.omarchy/package.json"
    ).read_text())
    assert metadata["source"] == "local"
    assert metadata["release_ring"] == "fast"
    assert set(metadata["channels"]) == {"edge", "rc", "stable"}

    desktop = (ROOT / "packaging/desktop/fam-os.desktop").read_text()
    assert "[Desktop Entry]" in desktop
    assert "Exec=fam-os console" in desktop
    assert "Icon=fam-os" in desktop
    core = (ROOT / "packaging/systemd/fam-os.service").read_text()
    bridge = (ROOT / "packaging/systemd/fam-os-desktop.service").read_text()
    assert "WantedBy=default.target" in core
    assert "After=graphical-session.target" in bridge
    assert "PartOf=graphical-session.target" in bridge
    assert "WantedBy=graphical-session.target" in bridge
    assert re.search(r"post_upgrade\(\)", (
        ROOT / "packaging/arch/fam-os.install"
    ).read_text())
    bootstrap = (ROOT / "packaging/omarchy/bootstrap.sh").read_text()
    fingerprint = (
        ROOT / "packaging/keys/fam-os-release.fingerprint"
    ).read_text().strip()
    assert fingerprint in bootstrap
    assert "SHA256SUMS.asc" in bootstrap and "$package_name.sig" in bootstrap

    forbidden = ("/home/demimagic", "/run/user/1000", "NewLLM/FAM_OS")
    release_paths = (
        ROOT / "packaging", ROOT / "integrations/omarchy",
        ROOT / "docs/installation/omarchy.md",
    )
    for release_path in release_paths:
        paths = release_path.rglob("*") if release_path.is_dir() else (release_path,)
        for path in paths:
            if path.is_file() and path.suffix not in {".png", ".jpg", ".jpeg"}:
                content = path.read_text(encoding="utf-8")
                assert not any(value in content for value in forbidden), str(path)
    print("Omarchy integration contract: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
