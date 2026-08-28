"""Human- and machine-readable Omarchy compatibility diagnostics."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import Callable
from urllib.request import Request, urlopen

from fam_os.adapters.omarchy.detection import OmarchyCapabilities, OmarchyDetector


class DiagnosticStatus(StrEnum):
    PASS = "pass"
    DEGRADED = "degraded"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class DiagnosticCheck:
    check_id: str
    status: DiagnosticStatus
    detail: str
    fix: str | None = None


@dataclass(frozen=True, slots=True)
class OmarchyDiagnosticReceipt:
    healthy: bool
    capabilities: OmarchyCapabilities
    checks: tuple[DiagnosticCheck, ...]

    def document(self) -> dict[str, object]:
        return asdict(self)


def diagnose_omarchy(
    detector: OmarchyDetector | None = None,
    *,
    service_probe: Callable[[], bool] | None = None,
    widget_probe: Callable[[], bool] | None = None,
) -> OmarchyDiagnosticReceipt:
    active_detector = detector or OmarchyDetector()
    capabilities = active_detector.detect()
    paths = capabilities.paths
    package_integrity = _package_integrity()
    codex = next((item for item in capabilities.agents if item.agent_id == "codex"), None)
    checks = [
        _check("host.omarchy", capabilities.host.omarchy, "Omarchy host detected", "Run this integration on Omarchy"),
        _check(
            "host.support", capabilities.host.supported,
            "Omarchy 4.x x86_64 is supported",
            "Use Omarchy 4.x x86_64; aarch64 requires explicit experimental mode",
            degraded=capabilities.host.support_level == "experimental",
        ),
        _check(
            "package.integrity", package_integrity is True,
            "Installed FAM package files pass pacman verification",
            "Reinstall fam-os with pacman", degraded=package_integrity is None,
        ),
        _check("desktop.graphical", capabilities.desktop.graphical, "Graphical session available", "Log in to the Omarchy graphical session"),
        _check("desktop.hyprland", capabilities.desktop.compositor == "hyprland", "Hyprland IPC available", "Start the Omarchy Hyprland session", degraded=True),
        _check("session.uwsm", capabilities.desktop.manager == "uwsm", "UWSM application launcher available", "Install or repair UWSM"),
        _check("shell.quickshell", capabilities.features.quickshell_plugins, "Omarchy Quickshell plugin support available", "Update Omarchy or repair its shell", degraded=True),
        _check("shell.ipc", _command_ok(("omarchy-shell", "shell", "listPlugins")), "Quickshell plugin IPC available", "Restart omarchy-shell", degraded=True),
        _check("desktop.portal", _portal_available(), "XDG Desktop Portal available", "Restart the Omarchy portal services", degraded=True),
        _check("application.browser", capabilities.features.browser_testing, "A supported browser is available", "Install Chromium or Firefox", degraded=True),
        _check("inference.endpoint", any(item.reachable for item in capabilities.inference), "A local inference endpoint is reachable", "Start Ollama or LM Studio", degraded=True),
        _check("inference.models", _inference_models_available(capabilities), "At least one local inference model is available", "Pull a FAM-compatible Ollama model", degraded=True),
        _check("agent.codex", bool(codex and codex.available), "Codex CLI is installed", "Install Codex or configure local inference", degraded=True),
        _check("agent.codex_auth", _codex_authenticated(codex), "Codex authentication is active", "Run codex login", degraded=True),
        _check("application.accessibility", _atspi_available(), "AT-SPI native application testing is available", "Install python-gobject and at-spi2-core, then restart the graphical session", degraded=True),
        _check("application.capture", capabilities.features.screen_capture, "Native application screen capture is available", "Install grim", degraded=True),
        _check("omarchy.snapshots", capabilities.features.system_snapshots, "Omarchy snapshot recovery is available", "Repair the Omarchy snapshot tools", degraded=True),
        _check("state.writable", _writable_location(paths.fam_state_root), "FAM state location is writable", "Repair the owner and permissions of the FAM state directory"),
        _check("runtime.writable", _writable_location(paths.fam_runtime_root), "FAM runtime location is writable", "Repair XDG_RUNTIME_DIR and restart the user session"),
        _check("candidate.health", _candidate_health(paths.fam_state_root), "Candidate workspaces are healthy", "Inspect or remove only the reported damaged candidate"),
        _check("agent.launcher", _command_available("omarchy-fam", paths.home), "FAM Omarchy agent launcher is available", "Run fam-os repair omarchy"),
        _check("agent.usage", _command_available("omarchy-agent-usage-fam", paths.home), "FAM usage collector is available", "Run fam-os repair omarchy", degraded=True),
    ]
    actual_service_probe = service_probe or (lambda: _service_healthy(paths.fam_runtime_root))
    actual_widget_probe = widget_probe or (
        lambda: (paths.plugin_root / "fam.os/manifest.json").is_file()
    )
    checks.append(_check("fam.service", actual_service_probe(), "FAM service is healthy", "Run fam-os repair omarchy --service"))
    checks.append(_check("fam.widget", actual_widget_probe(), "FAM widget is installed", "Run fam-os repair omarchy --widget", degraded=True))
    terminal_failures = [item for item in checks if item.status is DiagnosticStatus.FAILED]
    return OmarchyDiagnosticReceipt(not terminal_failures, capabilities, tuple(checks))


def _check(
    check_id: str, passed: bool, success: str, fix: str, *, degraded: bool = False,
) -> DiagnosticCheck:
    if passed:
        return DiagnosticCheck(check_id, DiagnosticStatus.PASS, success)
    status = DiagnosticStatus.DEGRADED if degraded else DiagnosticStatus.FAILED
    return DiagnosticCheck(check_id, status, success.replace(" available", " unavailable").replace(" detected", " not detected"), fix)


def _service_healthy(runtime_root: Path) -> bool:
    descriptor_path = runtime_root / "widget.json"
    try:
        descriptor = json.loads(descriptor_path.read_text(encoding="utf-8"))
        token = Path(descriptor["tokenPath"]).read_text(encoding="ascii").strip()
        request = Request(
            str(descriptor["endpoint"]).rstrip("/") + "/api/v1/status",
            headers={"X-FAM-Widget-Token": token},
        )
        with urlopen(request, timeout=2) as response:
            value = json.load(response)
        return response.status == 200 and value.get("service") == "healthy"
    except (KeyError, OSError, RuntimeError, ValueError):
        return False


def _atspi_available() -> bool:
    try:
        from fam_os.adapters.linux.accessibility import GiAtspiProvider
        return bool(GiAtspiProvider().available())
    except (ImportError, OSError, RuntimeError):
        return False


def _command_ok(command: tuple[str, ...]) -> bool:
    try:
        return subprocess.run(
            command, check=False, capture_output=True, text=True, timeout=5,
        ).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _command_available(name: str, home: Path) -> bool:
    local = home / ".local/bin" / name
    return shutil.which(name) is not None or (local.is_file() and os.access(local, os.X_OK))


def _portal_available() -> bool:
    try:
        result = subprocess.run(
            ("busctl", "--user", "--list"), check=False,
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0 and "org.freedesktop.portal.Desktop" in result.stdout


def _codex_authenticated(capability) -> bool:
    if capability is None or not capability.available or not capability.executable:
        return False
    return _command_ok((capability.executable, "login", "status"))


def _inference_models_available(capabilities: OmarchyCapabilities) -> bool:
    endpoints = [
        item for item in capabilities.inference
        if item.reachable and item.kind == "ollama"
    ]
    for endpoint in endpoints:
        if endpoint.models:
            return True
        try:
            with urlopen(endpoint.url.rstrip("/") + "/api/tags", timeout=2) as response:
                document = json.load(response)
            if response.status == 200 and document.get("models"):
                return True
        except (OSError, RuntimeError, ValueError):
            continue
    return False


def _package_integrity() -> bool | None:
    if not Path("/usr/share/fam-os/arch-package.json").is_file():
        return None
    return _command_ok(("pacman", "-Qkk", "fam-os"))


def _writable_location(path: Path) -> bool:
    current = path
    while not current.exists() and current != current.parent:
        current = current.parent
    return current.is_dir() and os.access(current, os.W_OK | os.X_OK)


def _candidate_health(state_root: Path) -> bool:
    root = state_root / "engineering/candidates"
    if not root.exists():
        return True
    if not root.is_dir() or not os.access(root, os.R_OK | os.X_OK):
        return False
    try:
        for index, path in enumerate(root.rglob("*")):
            if index >= 5_000:
                break
            if path.is_symlink():
                return False
    except OSError:
        return False
    return True
