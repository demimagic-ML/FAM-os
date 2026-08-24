"""Build, install, and run one ephemeral signed FAM_OS release."""

from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from fam_os.product.bundle_installation import SignedBundleInstallation
from fam_os.product.release_assembly import CompleteReleaseAssembler
from fam_os.product.vscode_installation import VsCodeConnectorInstallation


def build_and_install(
    repository: Path,
    root: Path,
    release_id: str = "phase19-exit",
    key_id: str = "phase19-test",
):
    wheelhouse = root / "wheelhouse"
    wheelhouse.mkdir()
    subprocess.run(
        (
            sys.executable, "-m", "pip", "wheel", str(repository),
            "--wheel-dir", str(wheelhouse), "--no-build-isolation",
        ),
        check=True, capture_output=True, text=True, timeout=300,
    )
    private_key = Ed25519PrivateKey.generate()
    bundle = root / "phase19-release"
    manifest = CompleteReleaseAssembler(repository).build(
        release_id, wheelhouse, bundle, key_id, private_key,
    )
    installation = SignedBundleInstallation(
        root / "installation", {key_id: private_key.public_key()},
    )
    receipt = installation.install(bundle)
    if not receipt.healthy:
        raise RuntimeError(f"signed release installation failed: {receipt.issues}")
    extensions = root / "extensions"
    connector = VsCodeConnectorInstallation(
        installation.prefix / "active", extensions,
    ).install()
    if not connector.installed:
        raise RuntimeError("signed VS Code connector did not install")
    return installation, manifest, connector, extensions


def configure_project(state_root: Path, project: Path) -> None:
    config = state_root / "config/os-tools.json"
    config.parent.mkdir(parents=True, mode=0o700)
    config.write_text(json.dumps({
        "contract_version": "fam.product.os-tools/v1alpha1",
        "projects": [{
            "project_id": "phase19", "display_name": "Phase 19 project",
            "root": str(project),
            "commands": [{
                "capability_id": "project.test",
                "display_name": "Run project tests",
                "executable": sys.executable,
                "arguments": ["-m", "unittest", "-v"],
            }],
        }],
    }, sort_keys=True), encoding="utf-8")
    os.chmod(config, 0o600)


class InstalledService:
    def __init__(self, installation, root: Path, ollama_url: str) -> None:
        self.root = root
        self.port = _free_port()
        self.runtime_root = root / "runtime"
        self._stdout = (root / "service.stdout").open("w", encoding="utf-8")
        self._stderr = (root / "service.stderr").open("w", encoding="utf-8")
        self._process = subprocess.Popen(
            (
                str(installation.prefix / "bin/fam-service"),
                "--state-root", str(root / "state"),
                "--runtime-root", str(self.runtime_root),
                "--external-ollama", "--ollama-url", ollama_url,
                "--console-port", str(self.port),
                "--ready-file", str(root / "ready"),
            ),
            stdout=self._stdout, stderr=self._stderr, text=True,
            start_new_session=True,
        )

    def wait_ready(self, timeout: float = 30) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if (self.root / "ready").is_file():
                return
            if self._process.poll() is not None:
                raise RuntimeError(self._failure("installed service exited"))
            time.sleep(0.05)
        raise TimeoutError(self._failure("installed service did not become ready"))

    def stop(self) -> None:
        if self._process.poll() is None:
            try:
                os.killpg(self._process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        try:
            self._process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            os.killpg(self._process.pid, signal.SIGKILL)
            self._process.wait(timeout=5)
        self._stdout.close()
        self._stderr.close()

    def _failure(self, prefix: str) -> str:
        self._stdout.flush()
        self._stderr.flush()
        stderr = (self.root / "service.stderr").read_text(errors="replace")[-4000:]
        return f"{prefix}: {stderr}"

    def __enter__(self):
        self.wait_ready()
        return self

    def __exit__(self, *_error):
        self.stop()


def _free_port() -> int:
    with socket.socket() as stream:
        stream.bind(("127.0.0.1", 0))
        return stream.getsockname()[1]
