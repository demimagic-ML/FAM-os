"""Idempotent installation lifecycle for FAM's Omarchy integration."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
import re
from dataclasses import dataclass
from pathlib import Path

from fam_os.adapters.omarchy.detection import OmarchyDetector
from fam_os.adapters.omarchy.diagnostics import diagnose_omarchy
from fam_os.adapters.omarchy.environment import OmarchyPaths, omarchy_paths


INTEGRATION_CONTRACT = "fam.omarchy.installation/v1"
PLUGIN_ID = "fam.os"
DEFAULT_PLUGIN_URL = "https://github.com/demimagic-ML/omarchy-fam-plugin.git"


@dataclass(frozen=True, slots=True)
class OmarchySetupReceipt:
    operation: str
    configured: bool
    service_enabled: bool
    desktop_entry_installed: bool
    widget_installed: bool
    widget_enabled: bool
    agent_launcher_installed: bool
    usage_collector_installed: bool
    engineering_provider: str
    manifest: str
    diagnostics: dict[str, object]
    issues: tuple[str, ...] = ()
    self_test_passed: bool = False
    onboarding_opened: bool = False
    menu_installed: bool = False
    post_update_hook_installed: bool = False


class OmarchySetup:
    def __init__(
        self,
        *,
        paths: OmarchyPaths | None = None,
        integration_root: Path | None = None,
        detector: OmarchyDetector | None = None,
        plugin_url: str | None = None,
        run=subprocess.run,
        which=shutil.which,
    ) -> None:
        self.paths = paths or omarchy_paths()
        self.integration_root = integration_root or _integration_root()
        self.detector = detector or OmarchyDetector()
        self.plugin_url = plugin_url or os.environ.get(
            "FAM_OS_OMARCHY_PLUGIN_URL",
            DEFAULT_PLUGIN_URL,
        )
        self._run = run
        self._which = which
        self.manifest_path = self.paths.fam_state_root / "omarchy/integration.json"

    def setup(
        self,
        *,
        enable_widget: bool = True,
        start: bool = True,
        allow_experimental: bool = False,
    ) -> OmarchySetupReceipt:
        capabilities = self.detector.detect()
        if not capabilities.host.omarchy:
            raise RuntimeError("Omarchy was not detected on this host")
        if not capabilities.host.supported and not (
            allow_experimental and capabilities.host.support_level == "experimental"
        ):
            raise RuntimeError(
                "FAM officially supports Omarchy 4.x on x86_64; "
                "aarch64 requires --allow-experimental",
            )
        issues = []
        desktop_installed = self._install_desktop_entry()
        launcher, collector = self._install_agent_commands()
        menu_installed = self._install_menu_extension()
        hook_installed = self._install_post_update_hook()
        provider = self._write_service_environment(capabilities)
        service_enabled = self._enable_services(start=start)
        widget_installed = False
        widget_enabled = False
        if enable_widget:
            widget_installed, widget_enabled = self._install_widget()
            if not widget_installed:
                issues.append("widget installation failed")
        self._write_manifest(
            {
                "contract_version": INTEGRATION_CONTRACT,
                "desktop_entry": desktop_installed,
                "services": [
                    "fam-os.service",
                    "fam-os-desktop.service",
                    "fam-os-usage.timer",
                ],
                "widget": widget_installed,
                "widget_enabled": widget_enabled,
                "widget_source": self.plugin_url,
                "integration_root": str(self.integration_root),
                "agent_launcher": launcher,
                "usage_collector": collector,
                "menu_extension": menu_installed,
                "post_update_hook": hook_installed,
                "engineering_provider": provider,
            }
        )
        diagnosis = (
            self._wait_for_diagnosis() if start else diagnose_omarchy(self.detector)
        )
        onboarding = self._open_onboarding() if start and diagnosis.healthy else False
        configured = (
            service_enabled
            and desktop_installed
            and launcher
            and collector
            and menu_installed
            and hook_installed
            and (not enable_widget or widget_installed and widget_enabled)
            and (not start or diagnosis.healthy)
        )
        return OmarchySetupReceipt(
            "setup",
            configured,
            service_enabled,
            desktop_installed,
            widget_installed,
            widget_enabled,
            launcher,
            collector,
            provider,
            str(self.manifest_path),
            diagnosis.document(),
            tuple(issues),
            diagnosis.healthy,
            onboarding,
            menu_installed,
            hook_installed,
        )

    def repair(
        self, *, widget: bool = False, service: bool = False
    ) -> OmarchySetupReceipt:
        if not widget and not service:
            widget = service = True
        desktop_installed = self._install_desktop_entry()
        capabilities = self.detector.detect()
        launcher, collector = self._install_agent_commands()
        menu_installed = self._install_menu_extension()
        hook_installed = self._install_post_update_hook()
        provider = self._write_service_environment(capabilities)
        service_enabled = (
            self._enable_services(start=True) if service else self._service_enabled()
        )
        widget_installed, widget_enabled = (
            self._install_widget(update=True) if widget else self._widget_status()
        )
        diagnosis = diagnose_omarchy(self.detector)
        self._write_manifest(
            {
                "contract_version": INTEGRATION_CONTRACT,
                "desktop_entry": desktop_installed,
                "services": [
                    "fam-os.service",
                    "fam-os-desktop.service",
                    "fam-os-usage.timer",
                ],
                "widget": widget_installed,
                "widget_enabled": widget_enabled,
                "widget_source": self.plugin_url,
                "integration_root": str(self.integration_root),
                "agent_launcher": launcher,
                "usage_collector": collector,
                "menu_extension": menu_installed,
                "post_update_hook": hook_installed,
                "engineering_provider": provider,
            }
        )
        configured = (
            service_enabled
            and desktop_installed
            and launcher
            and collector
            and menu_installed
            and hook_installed
            and (not widget or widget_installed and widget_enabled)
        )
        return OmarchySetupReceipt(
            "repair",
            configured,
            service_enabled,
            desktop_installed,
            widget_installed,
            widget_enabled,
            launcher,
            collector,
            provider,
            str(self.manifest_path),
            diagnosis.document(),
            (),
            False,
            False,
            menu_installed,
            hook_installed,
        )

    def remove(self) -> OmarchySetupReceipt:
        self._systemctl("disable", "--now", "fam-os-desktop.service", check=False)
        self._systemctl("disable", "--now", "fam-os-usage.timer", check=False)
        self._systemctl("disable", "--now", "fam-os.service", check=False)
        widget_installed, _enabled = self._widget_status()
        widget_path = self.paths.plugin_root / PLUGIN_ID
        if widget_installed and self._git_plugin_owned(widget_path):
            self._command(
                (
                    "omarchy",
                    "plugin",
                    "remove",
                    PLUGIN_ID,
                    "--yes",
                ),
                check=False,
            )
        desktop = self.paths.data_home / "applications/fam-os.desktop"
        if desktop.is_file() and _managed_desktop(desktop):
            desktop.unlink()
        self.manifest_path.unlink(missing_ok=True)
        for name in ("omarchy-fam", "omarchy-agent-usage-fam"):
            target = self.paths.home / ".local/bin" / name
            if target.is_file() and _managed_script(target):
                target.unlink()
        self._remove_menu_extension()
        self._remove_post_update_hook()
        diagnosis = diagnose_omarchy(self.detector)
        return OmarchySetupReceipt(
            "remove",
            False,
            False,
            False,
            False,
            False,
            False,
            False,
            "none",
            str(self.manifest_path),
            diagnosis.document(),
        )

    def purge_user_data(self, *, confirmed: bool) -> dict[str, object]:
        if not confirmed:
            raise PermissionError("purge requires --user-data and --yes")
        self.remove()
        targets = (
            self.paths.data_home / "fam-os",
            self.paths.config_home / "fam-os",
            self.paths.cache_home / "fam-os",
            self.paths.state_home / "fam-os",
            self.paths.runtime_dir / "fam-os",
        )
        removed: list[str] = []
        for target in targets:
            _purge_owned_tree(target, expected_name="fam-os")
            if not os.path.lexists(target):
                removed.append(str(target))
        usage = self.paths.usage_root / "fam.json"
        if usage.is_symlink():
            raise PermissionError("FAM usage record cannot be a symbolic link")
        if usage.is_file():
            if usage.stat(follow_symlinks=False).st_uid != os.geteuid():
                raise PermissionError("FAM usage record is not owned by this user")
            usage.unlink()
            removed.append(str(usage))
        return {"purged": True, "removed": removed, "userDataPreserved": False}

    def _install_desktop_entry(self) -> bool:
        source = self.integration_root / "desktop/fam-os.desktop"
        if not source.is_file():
            system_entry = Path("/usr/share/applications/fam-os.desktop")
            return system_entry.is_file()
        target = self.paths.data_home / "applications/fam-os.desktop"
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        content = source.read_bytes()
        if not target.is_file() or target.read_bytes() != content:
            temporary = target.with_suffix(".tmp")
            temporary.write_bytes(content)
            os.chmod(temporary, 0o644)
            os.replace(temporary, target)
        return True

    def _install_agent_commands(self) -> tuple[bool, bool]:
        commands = (
            ("launcher/omarchy-fam", "omarchy-fam"),
            ("usage-collector/omarchy-agent-usage-fam", "omarchy-agent-usage-fam"),
        )
        statuses = []
        target_root = self.paths.home / ".local/bin"
        target_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        for relative, name in commands:
            system = Path("/usr/bin") / name
            if system.is_file() and os.access(system, os.X_OK):
                statuses.append(True)
                continue
            source = self.integration_root / relative
            target = target_root / name
            if not source.is_file():
                statuses.append(False)
                continue
            content = source.read_text(encoding="utf-8")
            marker = "# X-FAM-Managed=true\n"
            if marker not in content:
                lines = content.splitlines(keepends=True)
                content = lines[0] + marker + "".join(lines[1:])
            temporary = target.with_suffix(".tmp")
            temporary.write_text(content, encoding="utf-8")
            os.chmod(temporary, 0o755)
            os.replace(temporary, target)
            statuses.append(True)
        return statuses[0], statuses[1]

    def _install_menu_extension(self) -> bool:
        source = self.integration_root / "menu/omarchy-menu.json"
        if not source.is_file():
            return False
        owned = json.loads(source.read_text(encoding="utf-8"))
        if (
            not isinstance(owned, dict)
            or not owned
            or any(key != "fam" and not key.startswith("fam.") for key in owned)
        ):
            raise RuntimeError("FAM Omarchy menu source is invalid")
        target = self.paths.config_home / "omarchy/extensions/omarchy-menu.jsonc"
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        current = _read_jsonc_object(target)
        current.update(owned)
        _write_json_object(target, current)
        return True

    def _remove_menu_extension(self) -> None:
        target = self.paths.config_home / "omarchy/extensions/omarchy-menu.jsonc"
        if not target.is_file():
            return
        current = _read_jsonc_object(target)
        remaining = {
            key: value
            for key, value in current.items()
            if key != "fam" and not key.startswith("fam.")
        }
        _write_json_object(target, remaining)

    def _install_post_update_hook(self) -> bool:
        source = self.integration_root / "hooks/fam-os"
        if not source.is_file():
            return False
        result = self._command(
            (
                "omarchy",
                "hook",
                "install",
                "post-update",
                str(source),
            ),
            check=False,
        )
        return result.returncode == 0

    def _remove_post_update_hook(self) -> None:
        target = self.paths.config_home / "omarchy/hooks/post-update.d/fam-os"
        if target.is_file() and _managed_script(target):
            target.unlink()

    def _write_service_environment(self, capabilities) -> str:
        endpoint = next(
            (
                item
                for item in capabilities.inference
                if item.reachable and item.kind == "ollama"
            ),
            None,
        )
        selected = next((item for item in capabilities.agents if item.selected), None)
        codex = next(
            (item for item in capabilities.agents if item.agent_id == "codex"), None
        )
        provider = (
            "codex-subscription"
            if selected is not None
            and selected.agent_id == "codex"
            and codex is not None
            and codex.available
            else "ollama"
        )
        values = {
            "FAM_OS_ENGINEERING_PROVIDER": provider,
            "FAM_OS_CONSOLE_PORT": "8765",
            "FAM_OS_EXTERNAL_OLLAMA": "true" if endpoint is not None else "false",
        }
        if endpoint is not None:
            values["FAM_OS_OLLAMA_URL"] = endpoint.url
        path = self.paths.config_home / "fam-os/service.env"
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        existing = _read_service_environment(path)
        values.update(existing)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            "".join(f"{key}={value}\n" for key, value in sorted(values.items()))
        )
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
        return values["FAM_OS_ENGINEERING_PROVIDER"]

    def _enable_services(self, *, start: bool) -> bool:
        self._systemctl("daemon-reload")
        arguments = ("enable", "--now") if start else ("enable",)
        core = self._systemctl(*arguments, "fam-os.service", check=False)
        desktop = self._systemctl(*arguments, "fam-os-desktop.service", check=False)
        usage = self._systemctl(*arguments, "fam-os-usage.timer", check=False)
        return (
            core.returncode == 0 and desktop.returncode == 0 and usage.returncode == 0
        )

    def _service_enabled(self) -> bool:
        return (
            self._systemctl("is-enabled", "fam-os.service", check=False).returncode == 0
        )

    def _install_widget(self, *, update: bool = False) -> tuple[bool, bool]:
        existing, enabled = self._widget_status()
        target = self.paths.plugin_root / PLUGIN_ID
        if not existing:
            result = self._command(
                (
                    "omarchy",
                    "plugin",
                    "add",
                    self.plugin_url,
                    "--enable",
                    "--yes",
                ),
                check=False,
            )
            if result.returncode != 0:
                return False, False
            self._require_verified_plugin(target)
            return self._widget_status(default=(True, True))
        if not self._git_plugin_owned(target):
            raise RuntimeError(
                f"{PLUGIN_ID} exists but is not the configured Git-backed FAM plugin",
            )
        self._require_verified_plugin(target)
        if update:
            result = self._command(
                (
                    "omarchy",
                    "plugin",
                    "update",
                    PLUGIN_ID,
                    "--yes",
                ),
                check=False,
            )
            if result.returncode != 0:
                return True, enabled
            self._require_verified_plugin(target)
        if not enabled:
            result = self._command(
                (
                    "omarchy",
                    "plugin",
                    "enable",
                    PLUGIN_ID,
                ),
                check=False,
            )
            if result.returncode != 0:
                return True, False
        return self._widget_status(default=(True, True))

    def _widget_status(self, default=(False, False)) -> tuple[bool, bool]:
        target = self.paths.plugin_root / PLUGIN_ID
        if target.is_dir():
            result = self._command(("omarchy", "plugin", "list", "--json"), check=False)
            if result.returncode == 0:
                try:
                    records = json.loads(result.stdout)
                    entries = (
                        records
                        if isinstance(records, list)
                        else records.get("plugins", [])
                    )
                    match = next(
                        (item for item in entries if item.get("id") == PLUGIN_ID), None
                    )
                    return True, bool(match and match.get("enabled"))
                except (AttributeError, json.JSONDecodeError):
                    pass
            return True, default[1]
        return default

    def _git_plugin_owned(self, target: Path) -> bool:
        if not (target / ".git").exists():
            return False
        result = self._command(
            (
                "git",
                "-C",
                str(target),
                "remote",
                "get-url",
                "origin",
            ),
            check=False,
        )
        return result.returncode == 0 and _same_git_url(
            result.stdout.strip(),
            self.plugin_url,
        )

    def _require_verified_plugin(self, target: Path) -> None:
        key = _release_public_key()
        if not key.is_file():
            raise RuntimeError("FAM release public key is unavailable")
        temporary_root = self.paths.fam_runtime_root
        temporary_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        with tempfile.TemporaryDirectory(
            prefix="plugin-trust-",
            dir=temporary_root,
        ) as directory:
            environment = dict(os.environ)
            environment["GNUPGHOME"] = directory
            imported = self._command(
                ("gpg", "--batch", "--import", str(key)),
                check=False,
                env=environment,
            )
            if imported.returncode != 0:
                raise RuntimeError("could not import the pinned FAM release key")
            verified = self._command(
                (
                    "git",
                    "-C",
                    str(target),
                    "verify-commit",
                    "HEAD",
                ),
                check=False,
                env=environment,
            )
            if verified.returncode != 0:
                raise RuntimeError(
                    "FAM plugin HEAD is not signed by the pinned release key"
                )

    def _write_manifest(self, document: dict[str, object]) -> None:
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporary = self.manifest_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
        os.chmod(temporary, 0o600)
        os.replace(temporary, self.manifest_path)

    def _wait_for_diagnosis(self, timeout_seconds: float = 10.0):
        deadline = time.monotonic() + timeout_seconds
        receipt = diagnose_omarchy(self.detector)
        while not receipt.healthy and time.monotonic() < deadline:
            time.sleep(0.25)
            receipt = diagnose_omarchy(self.detector)
        return receipt

    def _open_onboarding(self) -> bool:
        executable = self._which("fam-os")
        if executable is None:
            return False
        result = self._command(
            (
                executable,
                "console",
                "--runtime-root",
                str(self.paths.fam_runtime_root),
                "--port",
                "8765",
            ),
            check=False,
        )
        return result.returncode == 0

    def _systemctl(self, *arguments: str, check: bool = True):
        return self._command(("systemctl", "--user", *arguments), check=check)

    def _command(
        self,
        command: tuple[str, ...],
        *,
        check: bool = True,
        env: dict[str, str] | None = None,
    ):
        return self._run(
            command,
            capture_output=True,
            text=True,
            timeout=120,
            check=check,
            env=env,
        )


def _integration_root() -> Path:
    configured = os.environ.get("FAM_OS_OMARCHY_INTEGRATION_ROOT")
    if configured:
        return Path(configured)
    installed = Path("/usr/share/fam-os/omarchy")
    if installed.is_dir():
        return installed
    return Path(__file__).resolve().parents[3] / "integrations/omarchy"


def _managed_desktop(path: Path) -> bool:
    try:
        return "X-FAM-Managed=true" in path.read_text(encoding="utf-8")
    except OSError:
        return False


def _managed_script(path: Path) -> bool:
    try:
        return "X-FAM-Managed=true" in path.read_text(encoding="utf-8")[:512]
    except OSError:
        return False


def _read_jsonc_object(path: Path) -> dict[str, object]:
    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    without_comments = _strip_jsonc_comments(content)
    normalized = re.sub(r",\s*([}\]])", r"\1", without_comments)
    try:
        value = json.loads(normalized or "{}")
    except json.JSONDecodeError as error:
        raise RuntimeError(
            f"Omarchy menu extension is invalid JSONC: {path}"
        ) from error
    if not isinstance(value, dict):
        raise RuntimeError("Omarchy menu extension must contain an object")
    return value


def _strip_jsonc_comments(content: str) -> str:
    """Remove JSONC comments without treating comment markers in strings as syntax."""
    result: list[str] = []
    index = 0
    in_string = False
    escaped = False
    while index < len(content):
        character = content[index]
        following = content[index + 1] if index + 1 < len(content) else ""
        if in_string:
            result.append(character)
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            index += 1
            continue
        if character == '"':
            in_string = True
            result.append(character)
            index += 1
            continue
        if character == "/" and following == "/":
            index += 2
            while index < len(content) and content[index] not in "\r\n":
                index += 1
            continue
        if character == "/" and following == "*":
            index += 2
            while index + 1 < len(content) and content[index : index + 2] != "*/":
                if content[index] in "\r\n":
                    result.append(content[index])
                index += 1
            index = min(len(content), index + 2)
            continue
        result.append(character)
        index += 1
    if in_string:
        return content
    return "".join(result)


def _write_json_object(path: Path, value: dict[str, object]) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        "// FAM updates only entries whose ids are fam or fam.*.\n"
        + json.dumps(value, indent=2, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)


def _read_service_environment(path: Path) -> dict[str, str]:
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    allowed = {
        "FAM_OS_CODEX_MODEL",
        "FAM_OS_CONSOLE_PORT",
        "FAM_OS_ENGINEERING_MODEL",
        "FAM_OS_ENGINEERING_PROVIDER",
        "FAM_OS_EXTERNAL_OLLAMA",
        "FAM_OS_MODEL",
        "FAM_OS_OLLAMA_EXECUTABLE",
        "FAM_OS_OLLAMA_URL",
    }
    result = {}
    for raw in content.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if separator and key in allowed and value and "\n" not in value:
            result[key] = value
    return result


def _same_git_url(first: str, second: str) -> bool:
    def normalize(value: str) -> str:
        result = value.strip().removesuffix("/").removesuffix(".git")
        if result.startswith("git@github.com:"):
            result = "https://github.com/" + result.split(":", 1)[1]
        return result.casefold()

    return normalize(first) == normalize(second)


def _release_public_key() -> Path:
    installed = Path("/usr/share/fam-os/keys/fam-os-release.asc")
    if installed.is_file():
        return installed
    return Path(__file__).resolve().parents[3] / "packaging/keys/fam-os-release.asc"


def _purge_owned_tree(path: Path, *, expected_name: str) -> None:
    if path.name != expected_name or path == path.parent or path == Path.home():
        raise ValueError(f"refusing unsafe purge target: {path}")
    if not os.path.lexists(path):
        return
    if path.is_symlink():
        raise PermissionError(f"purge target cannot be a symbolic link: {path}")
    details = path.stat(follow_symlinks=False)
    if details.st_uid != os.geteuid() or not path.is_dir():
        raise PermissionError(f"purge target must be an owned directory: {path}")
    shutil.rmtree(path)
