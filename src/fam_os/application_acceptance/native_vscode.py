"""Isolated launcher and Core provider for the real VS Code connector."""

import json
import os
import signal
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from fam_os.applications import ApplicationCapabilityRegistry
from fam_os.applications.transport import (
    ConnectorRequestBroker, PeerAuthorizationPolicy, UnixApplicationServer,
    UnixEndpointConfiguration,
)


class IsolatedVsCodeHost:
    def __init__(self, code_path: Path, extension_path: Path, timeout_seconds=30.0):
        if not code_path.is_absolute() or not extension_path.is_absolute():
            raise ValueError("VS Code host paths must be absolute")
        self.code_path = code_path
        self.extension_path = extension_path
        self.timeout_seconds = timeout_seconds
        self.registry = ApplicationCapabilityRegistry()
        self.broker = ConnectorRequestBroker(
            self.registry, timeout_seconds=timeout_seconds,
        )
        self._temporary = None
        self._server = None
        self._thread = None
        self._process = None
        self._profile_root = None

    def start(self, workspace: Path, active_file: Path):
        if self._process is not None:
            raise RuntimeError("VS Code host is already started")
        workspace = workspace.resolve(strict=True)
        active_file = active_file.resolve(strict=True)
        if workspace not in active_file.parents:
            raise ValueError("active file must belong to the workspace")
        self._temporary = tempfile.TemporaryDirectory(prefix="fam-vscode-")
        root = Path(self._temporary.name)
        self._profile_root = root
        os.chmod(root, 0o700)
        socket_path = root / "applications.sock"
        self._server = UnixApplicationServer(
            UnixEndpointConfiguration(socket_path),
            PeerAuthorizationPolicy(os.geteuid()), self.broker,
        )
        self._server.open()
        self._thread = threading.Thread(target=self._server.serve_once, daemon=True)
        self._thread.start()
        user_data, extensions = self._profile(root, socket_path)
        self._process = subprocess.Popen(
            self._command(user_data, extensions, workspace, active_file),
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, start_new_session=True,
        )
        self._wait_registration()
        return self

    @property
    def connector_id(self):
        registrations = self.registry.snapshot().registrations
        if len(registrations) != 1:
            raise RuntimeError("VS Code connector registration is unavailable")
        return registrations[0].connector_id

    @property
    def instance_id(self):
        registrations = self.registry.snapshot().registrations
        if len(registrations) != 1:
            raise RuntimeError("VS Code connector registration is unavailable")
        return registrations[0].instance.instance_id

    def capability(self, instance_id, capability_id):
        return self.registry.lookup(instance_id, capability_id)

    def observe(self, request):
        return self.broker.observe(self.connector_id, request)

    def prepare_action(self, request):
        return self.broker.prepare_action(self.connector_id, request)

    def execute_action(self, proposal, confirmation):
        if proposal.request.instance_id != self.instance_id:
            raise ValueError("VS Code proposal belongs to another instance")
        return self.broker.execute_action(self.connector_id, confirmation)

    def stop(self):
        process, self._process = self._process, None
        if process is not None and process.poll() is None:
            _terminate_group(process)
        if self._profile_root is not None:
            _terminate_profile_processes(self._profile_root)
            self._profile_root = None
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None
        if self._server is not None:
            self._server.close()
            self._server = None
        if self._temporary is not None:
            self._temporary.cleanup()
            self._temporary = None

    def __enter__(self):
        return self

    def __exit__(self, *_error):
        self.stop()

    def _profile(self, root, socket_path):
        user_data = root / "user-data"
        settings = user_data / "User" / "settings.json"
        settings.parent.mkdir(parents=True)
        extensions = root / "extensions"
        extensions.mkdir()
        settings.write_text(json.dumps({
            "famOS.connector.autoConnect": True,
            "famOS.connector.socketPath": str(socket_path),
            "security.workspace.trust.enabled": False,
        }), encoding="utf-8")
        return user_data, extensions

    def _command(self, user_data, extensions, workspace, active_file):
        return (
            str(self.code_path), "--new-window", "--wait",
            f"--user-data-dir={user_data}", f"--extensions-dir={extensions}",
            f"--extensionDevelopmentPath={self.extension_path}",
            str(workspace), "--goto", f"{active_file}:1:1",
        )

    def _wait_registration(self):
        deadline = time.monotonic() + self.timeout_seconds
        while time.monotonic() < deadline:
            if self.registry.snapshot().registrations:
                return
            if self._process.poll() is not None:
                break
            time.sleep(0.05)
        self.stop()
        raise TimeoutError("VS Code semantic connector did not register")


def _terminate_group(process):
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=8)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=5)


def _terminate_profile_processes(profile_root):
    marker = str(profile_root).encode()
    process_ids = []
    for path in Path("/proc").glob("[0-9]*"):
        try:
            if path.stat().st_uid != os.geteuid():
                continue
            arguments = (path / "cmdline").read_bytes().split(b"\0")
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
        if any(marker in item for item in arguments):
            process_ids.append(int(path.name))
    for process_id in process_ids:
        try:
            os.kill(process_id, signal.SIGTERM)
        except ProcessLookupError:
            pass
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline and any(
        Path(f"/proc/{process_id}").exists() for process_id in process_ids
    ):
        time.sleep(0.05)
    for process_id in process_ids:
        try:
            os.kill(process_id, signal.SIGKILL)
        except ProcessLookupError:
            pass
