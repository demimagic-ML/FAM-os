"""Stateful Hyprland and AT-SPI testing tools for native Omarchy apps."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time
from uuid import uuid4

from fam_os.adapters.hyprland.windows import HyprlandWindowDiscovery, HyprlandWindowSettings
from fam_os.adapters.linux.accessibility import AccessibilityBridgePolicy, GiAtspiProvider, LinuxAccessibilityBridge
from fam_os.adapters.omarchy.session import UwsmApplicationLauncher
from fam_os.applications import AccessibleObjectRef
from fam_os.core.agent import AgentToolDescriptor, AgentToolEffect, AgentToolExecution, AgentToolRegistry


@dataclass(slots=True)
class NativeApplicationSession:
    session_id: str
    application_id: str
    process_id: int
    window_id: str
    command: tuple[str, ...]
    artifact_root: str
    status: str = "running"
    actions: int = 0
    assertions: int = 0
    passed_assertions: int = 0


class NativeApplicationTestTools:
    """Own launch, semantic interaction, evidence, assertions, and cleanup."""

    def __init__(self, workspace_root: Path, *, launcher=None, discovery=None, provider_factory=GiAtspiProvider, sleeper=time.sleep) -> None:
        self.root = workspace_root.resolve(strict=True)
        self.artifacts = self.root / ".fam-test-artifacts"
        self._launcher = launcher or UwsmApplicationLauncher()
        self._discovery = discovery or HyprlandWindowDiscovery(HyprlandWindowSettings(
            os.environ.get("XDG_SESSION_TYPE", "unknown"),
            bool(os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")), include_titles=True,
        ))
        self._provider_factory = provider_factory
        self._sleep = sleeper
        self._bridge = None
        self.session: NativeApplicationSession | None = None
        self._refs: dict[str, AccessibleObjectRef] = {}

    def register(self, registry: AgentToolRegistry) -> None:
        self._register(registry, "native_app_start", "Launch one native Omarchy application through UWSM, bind its new Hyprland window and AT-SPI tree, and return a semantic snapshot.", AgentToolEffect.APPLICATION_TEST, {"application_id": {"type": "string"}, "command": {"type": "array", "items": {"type": "string"}}, "timeout_seconds": {"type": "number"}}, self.start, ("application_id", "command"), self.available)
        self._register(registry, "native_app_snapshot", "Read the bounded AT-SPI tree for the active native application.", AgentToolEffect.OBSERVE, {}, self.snapshot, (), self.active)
        self._register(registry, "native_app_action", "Invoke an advertised action on one current AT-SPI element reference and return the resulting tree.", AgentToolEffect.APPLICATION_TEST, {"ref": {"type": "string"}, "action": {"type": "string"}}, self.action, ("ref", "action"), self.active)
        self._register(registry, "native_app_screenshot", "Capture the active Hyprland window with grim as visual evidence.", AgentToolEffect.APPLICATION_TEST, {"name": {"type": "string"}}, self.screenshot, (), self.active)
        self._register(registry, "native_app_assert", "Assert text, role, or element presence in the current native-app snapshot.", AgentToolEffect.APPLICATION_TEST, {"kind": {"type": "string", "enum": ["text", "role", "element"]}, "expected": {"type": "string"}, "ref": {"type": "string"}}, self.assert_outcome, ("kind", "expected"), self.active)
        self._register(registry, "native_app_stop", "Persist final evidence and terminate only the process owned by this test session.", AgentToolEffect.APPLICATION_TEST, {}, self.stop, (), self.active)

    def available(self) -> bool:
        try:
            return bool(self._provider_factory().available()) and not self._discovery.discover().issues
        except (ImportError, OSError, RuntimeError):
            return False

    def active(self) -> bool:
        return self.session is not None and self.session.status == "running"

    @property
    def all_checks_passed(self) -> bool:
        return bool(
            self.session is not None
            and self.session.assertions > 0
            and self.session.assertions == self.session.passed_assertions
        )

    @property
    def summary(self) -> dict[str, object] | None:
        return None if self.session is None else asdict(self.session)

    def start(self, arguments: dict[str, object]) -> str:
        if self.active():
            raise RuntimeError("a native application test session is already active")
        application_id = _text(arguments, "application_id")
        command = _command(arguments.get("command"))
        timeout = _timeout(arguments.get("timeout_seconds", 30))
        before = {item.window_id for item in self._discovery.discover().windows}
        receipt = self._launcher.launch(command)
        if receipt.returncode != 0:
            raise RuntimeError(receipt.stderr or "native application launch failed")
        deadline, window = time.monotonic() + timeout, None
        while time.monotonic() < deadline:
            candidates = [item for item in self._discovery.discover().windows if item.window_id not in before and item.process_id]
            if candidates:
                window = candidates[-1]
                break
            self._sleep(0.2)
        if window is None or window.process_id is None:
            raise RuntimeError("launched application did not create a Hyprland window")
        self._bridge = LinuxAccessibilityBridge(self._provider_factory(), AccessibilityBridgePolicy())
        identifier = f"native-app-{uuid4().hex}"
        artifact_root = self.artifacts / identifier
        artifact_root.mkdir(parents=True, exist_ok=False)
        self.session = NativeApplicationSession(identifier, application_id, window.process_id, window.window_id, command, str(artifact_root.relative_to(self.root)))
        snapshot = self._snapshot()
        self._persist(snapshot)
        return _encode(snapshot)

    def snapshot(self, _arguments: dict[str, object]) -> str:
        snapshot = self._snapshot()
        self._persist(snapshot)
        return _encode(snapshot)

    def action(self, arguments: dict[str, object]) -> AgentToolExecution:
        bridge, session = self._require()
        reference = self._refs.get(_text(arguments, "ref"))
        if reference is None:
            raise ValueError("native application element reference is stale")
        proposal = bridge.prepare_action(f"native-action-{uuid4().hex}", reference, _text(arguments, "action"))
        evidence = bridge.perform_action(proposal)
        session.actions += 1
        snapshot = self._snapshot()
        self._persist(snapshot)
        return AgentToolExecution(_encode({"evidence": asdict(evidence), "snapshot": snapshot}), {"verified": evidence.invoked, "operation": "native_application_action", "process_id": session.process_id})

    def screenshot(self, arguments: dict[str, object]) -> AgentToolExecution:
        _bridge, session = self._require()
        path = self.root / session.artifact_root / f"{_safe_name(str(arguments.get('name') or 'native-app'))}.png"
        executable = shutil.which("grim")
        if executable is None:
            raise FileNotFoundError("grim is required for native app screenshots")
        result = subprocess.run((executable, "-g", _window_geometry(session.process_id), str(path)), check=False, capture_output=True, text=True, timeout=30)
        if result.returncode != 0 or not path.is_file() or path.stat().st_size == 0:
            raise RuntimeError(result.stderr or "native app screenshot failed")
        relative = str(path.relative_to(self.root))
        return AgentToolExecution(_encode({"screenshot": relative}), {"verified": True, "operation": "native_application_screenshot", "path": relative})

    def assert_outcome(self, arguments: dict[str, object]) -> AgentToolExecution:
        _bridge, session = self._require()
        kind, expected = _text(arguments, "kind"), _text(arguments, "expected")
        ref = arguments.get("ref")
        snapshot = self._snapshot()
        nodes = snapshot["nodes"]
        if kind == "text":
            passed = any(expected in str(item.get("text") or item.get("name") or "") for item in nodes)
        elif kind == "role":
            passed = any(item.get("role") == expected for item in nodes)
        elif kind == "element":
            passed = isinstance(ref, str) and any(item.get("ref") == ref for item in nodes)
        else:
            raise ValueError("native assertion kind is invalid")
        session.assertions += 1
        session.passed_assertions += int(passed)
        self._persist(snapshot)
        receipt = {"kind": kind, "expected": expected, "ref": ref, "passed": passed}
        return AgentToolExecution(_encode(receipt), {"verified": passed, "operation": "native_application_assertion", "process_id": session.process_id})

    def stop(self, _arguments: dict[str, object]) -> AgentToolExecution:
        _bridge, session = self._require()
        snapshot = self._snapshot()
        if _owned_process(session.process_id):
            try:
                os.kill(session.process_id, signal.SIGTERM)
            except ProcessLookupError:
                pass
        session.status = "completed"
        self._persist(snapshot)
        verified = session.assertions > 0 and session.assertions == session.passed_assertions
        return AgentToolExecution(_encode({"status": session.status, "assertions": session.assertions, "passed_assertions": session.passed_assertions, "artifact_root": session.artifact_root}), {"verified": verified, "operation": "native_application_test_session", "process_id": session.process_id})

    def cleanup(self) -> None:
        if self.active():
            try:
                self.stop({})
            except Exception:
                pass

    def _snapshot(self) -> dict[str, object]:
        bridge, session = self._require()
        value = bridge.observe(session.process_id, include_text=True)
        self._refs.clear()
        nodes = []
        for node in value.nodes:
            reference = node.reference
            self._refs[reference.reference_id] = reference
            nodes.append({"ref": reference.reference_id, "parent": node.parent_reference_id, "depth": node.depth, "role": node.role, "name": node.name, "description": node.description, "states": list(node.states), "actions": [item.name for item in node.actions], "text": node.text})
        return {"session_id": session.session_id, "application_id": session.application_id, "process_id": session.process_id, "window_id": session.window_id, "nodes": nodes, "node_count": len(nodes), "truncated": value.truncated, "issue": value.issue_code}

    def _persist(self, snapshot: dict[str, object]) -> None:
        if self.session is not None:
            path = self.root / self.session.artifact_root / "session.json"
            temporary = path.with_suffix(".tmp")
            temporary.write_text(
                _encode({"session": asdict(self.session), "snapshot": snapshot}) + "\n",
                encoding="utf-8",
            )
            os.chmod(temporary, 0o600)
            os.replace(temporary, path)

    def _require(self):
        if not self.active() or self._bridge is None or self.session is None:
            raise RuntimeError("no active native application test session")
        return self._bridge, self.session

    @staticmethod
    def _register(registry, tool_id, description, effect, properties, implementation, required, available) -> None:
        registry.register(AgentToolDescriptor(tool_id, description, effect, {"type": "object", "properties": properties, "required": list(required), "additionalProperties": False}), implementation, available=available)


def _window_geometry(process_id: int) -> str:
    result = subprocess.run(("hyprctl", "-j", "clients"), check=False, capture_output=True, text=True, timeout=10)
    if result.returncode != 0:
        raise RuntimeError("Hyprland window geometry is unavailable")
    values = json.loads(result.stdout)
    match = next((item for item in values if item.get("pid") == process_id), None)
    if not isinstance(match, dict):
        raise RuntimeError("native app window is unavailable")
    at, size = match.get("at"), match.get("size")
    if not (isinstance(at, list) and isinstance(size, list) and len(at) == len(size) == 2 and all(isinstance(item, int) for item in at + size)):
        raise RuntimeError("native app window geometry is invalid")
    return f"{at[0]},{at[1]} {size[0]}x{size[1]}"


def _owned_process(process_id: int) -> bool:
    try:
        return Path(f"/proc/{process_id}").stat().st_uid == os.geteuid()
    except OSError:
        return False


def _command(value: object) -> tuple[str, ...]:
    if not isinstance(value, list) or not value or any(not isinstance(item, str) or not item for item in value):
        raise ValueError("command must be a non-empty string array")
    return tuple(value)


def _text(arguments: dict[str, object], key: str) -> str:
    value = arguments.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be non-empty text")
    return value.strip()


def _timeout(value: object) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not 1 <= value <= 300:
        raise ValueError("timeout_seconds must be between 1 and 300")
    return float(value)


def _safe_name(value: str) -> str:
    normalized = "".join(character if character.isalnum() or character in "-_" else "-" for character in value.strip())
    if not normalized:
        raise ValueError("screenshot name is invalid")
    return normalized[:80]


def _encode(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)[:262_144]
