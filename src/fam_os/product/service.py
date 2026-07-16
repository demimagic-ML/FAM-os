"""Production composition for the owner-scoped Shell, Core, Ollama, and Console."""

from __future__ import annotations

import argparse
import os
import signal
import socket
import threading
from dataclasses import dataclass
from pathlib import Path

from fam_os.adapters.ollama import OllamaRuntime, OllamaSettings
from fam_os.adapters.shell import (
    ShellRequestDispatcher, UnixShellServer, UnixShellServerConfiguration,
)
from fam_os.applications.transport import PeerAuthorizationPolicy
from fam_os.console.http import ConsoleHttpServer
from fam_os.console.provider import LocalConsoleProvider
from fam_os.console.service import load_or_create_token
from fam_os.core.ingress.local_chat_gateway import LocalInferenceShellGateway
from fam_os.product.user_isolation import PrivateUserRuntime, UserRuntimeIdentity


@dataclass(frozen=True, slots=True)
class ProductServiceSettings:
    state_root: Path
    runtime_root: Path
    model_ref: str = "qwen3:1.7b"
    ollama_url: str = "http://127.0.0.1:11434"
    console_port: int = 8765
    ready_file: Path | None = None


class LocalProductService:
    def __init__(self, settings: ProductServiceSettings, runtime=None) -> None:
        self.settings = settings
        self._runtime = runtime or OllamaRuntime(OllamaSettings(settings.ollama_url, 180))
        self._stop = threading.Event()
        self._shell_thread: threading.Thread | None = None
        self._console_thread: threading.Thread | None = None
        self.shell_server: UnixShellServer | None = None
        self.console_server: ConsoleHttpServer | None = None

    def start(self) -> None:
        self._initialize_roots()
        gateway = LocalInferenceShellGateway(self._runtime, self.settings.model_ref)
        self.shell_server = UnixShellServer(
            UnixShellServerConfiguration(self.settings.runtime_root / "shell.sock"),
            PeerAuthorizationPolicy(os.geteuid()), ShellRequestDispatcher(gateway),
        )
        token = load_or_create_token(self.settings.runtime_root / "console.token")
        self.console_server = ConsoleHttpServer(
            ("127.0.0.1", self.settings.console_port),
            LocalConsoleProvider(self.settings.state_root, self.settings.model_ref), token,
        )
        self.shell_server.open()
        self._shell_thread = threading.Thread(target=self._serve_shell, daemon=True)
        self._console_thread = threading.Thread(
            target=self.console_server.serve_forever, daemon=True,
        )
        self._shell_thread.start()
        self._console_thread.start()
        if self.settings.ready_file is not None:
            self.settings.ready_file.write_text("ready\n")

    def wait(self) -> None:
        self._stop.wait()

    def stop(self) -> None:
        self._stop.set()
        if self.console_server is not None:
            self.console_server.shutdown()
            self.console_server.server_close()
        if self.shell_server is not None:
            _wake_shell(self.settings.runtime_root / "shell.sock")
            self.shell_server.close()
        for thread in (self._shell_thread, self._console_thread):
            if thread is not None:
                thread.join(timeout=5)
        if self.settings.ready_file is not None:
            self.settings.ready_file.unlink(missing_ok=True)

    def _initialize_roots(self) -> None:
        PrivateUserRuntime(
            self.settings.state_root,
            UserRuntimeIdentity(str(os.geteuid()), os.geteuid()),
        ).initialize()
        self.settings.runtime_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.settings.runtime_root, 0o700)
        for name in ("experts", "permissions"):
            path = self.settings.state_root / name
            path.mkdir(exist_ok=True, mode=0o700)
            os.chmod(path, 0o700)

    def _serve_shell(self) -> None:
        server = self.shell_server
        if server is None:
            raise RuntimeError("shell server is not initialized")
        while not self._stop.is_set():
            try:
                server.serve_once()
            except (EOFError, OSError, RuntimeError):
                if not self._stop.is_set():
                    self._stop.set()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="FAM_OS local product service")
    parser.add_argument("--state-root", type=Path, default=_state_root())
    parser.add_argument("--runtime-root", type=Path, default=_runtime_root())
    parser.add_argument("--model", default="qwen3:1.7b")
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--console-port", type=int, default=8765)
    parser.add_argument("--ready-file", type=Path)
    args = parser.parse_args(argv)
    service = LocalProductService(ProductServiceSettings(
        args.state_root.absolute(), args.runtime_root.absolute(), args.model,
        args.ollama_url, args.console_port, args.ready_file,
    ))
    for event in (signal.SIGINT, signal.SIGTERM):
        signal.signal(event, lambda *_args: service.stop())
    try:
        service.start()
        service.wait()
    finally:
        service.stop()
    return 0


def _state_root() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "fam-os"


def _runtime_root() -> Path:
    return Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.geteuid()}")) / "fam-os"


def _wake_shell(path: Path) -> None:
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as stream:
            stream.connect(str(path))
    except OSError:
        pass


if __name__ == "__main__":
    raise SystemExit(main())
