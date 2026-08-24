"""Bounded local-file responsive capture through an external browser tool."""

import hashlib
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ResponsiveCapture:
    viewport_width: int
    viewport_height: int
    png_sha256: str
    browser_version: str
    network_policy: str


class LocalResponsiveBrowserCapture:
    def __init__(self, browser: Path = Path("/usr/bin/google-chrome")) -> None:
        if not browser.is_absolute() or not browser.is_file():
            raise ValueError("responsive capture browser is unavailable")
        self._browser = browser

    def capture(self, candidate_root: Path, relative_html: str, output: Path, *, width: int, height: int) -> ResponsiveCapture:
        root = candidate_root.resolve(strict=True)
        page = (root / relative_html).resolve(strict=True)
        target = output.resolve(strict=False)
        if root not in page.parents or page.is_symlink() or not page.is_file():
            raise PermissionError("browser capture page escapes candidate workspace")
        if root not in target.parents or target.is_symlink():
            raise PermissionError("browser capture output escapes candidate workspace")
        if width < 240 or height < 240 or width * height > 16_000_000:
            raise ValueError("responsive viewport exceeds policy")
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="fam-browser-profile-") as profile:
            command = (
                str(self._browser), "--headless=new", "--no-first-run",
                "--disable-extensions", "--disable-background-networking",
                "--disable-component-update", "--disable-sync",
                "--metrics-recording-only", "--mute-audio",
                "--host-resolver-rules=MAP * ~NOTFOUND",
                f"--user-data-dir={profile}",
                f"--window-size={width},{height}",
                f"--screenshot={target}", page.as_uri(),
            )
            result = subprocess.run(
                command, capture_output=True, text=True, timeout=30,
                env={"PATH": "/usr/bin:/bin", "HOME": profile},
            )
        if result.returncode or not target.is_file() or target.stat().st_size > 20 * 1024**2:
            raise RuntimeError("responsive browser capture failed within bounds")
        version = subprocess.run(
            (str(self._browser), "--version"), capture_output=True, text=True,
            timeout=5, env={"PATH": "/usr/bin:/bin", "HOME": "/nonexistent"},
        )
        return ResponsiveCapture(
            width, height, hashlib.sha256(target.read_bytes()).hexdigest(),
            version.stdout.strip(), "external-network-resolution-denied",
        )
