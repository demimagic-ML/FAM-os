"""Bounded local Ollama model creation for a disabled specialist canary."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

from fam_os.adapters.ollama.transport import JsonTransport, UrllibJsonTransport


class OllamaCanaryModelInstaller:
    def __init__(
        self, ollama: Path, base_url: str, timeout_seconds: int = 600,
        transport: JsonTransport | None = None,
    ) -> None:
        self._ollama = ollama
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._transport = transport or UrllibJsonTransport()

    def create(self, model_ref: str, modelfile: Path) -> str:
        if not modelfile.is_file() or modelfile.is_symlink():
            raise ValueError("canary Modelfile is unavailable")
        result = subprocess.run(
            (str(self._ollama), "create", model_ref, "-f", str(modelfile)),
            check=False, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            timeout=self._timeout, env=self._environment(),
        )
        if result.returncode != 0:
            raise RuntimeError("Ollama canary model creation failed")
        try:
            manifest = self._transport.request(
                "POST", f"{self._base_url}/api/show",
                {"model": model_ref, "verbose": False}, 60,
            )
            payload = json.dumps(
                manifest, sort_keys=True, separators=(",", ":"),
            ).encode()
            if len(payload) > 4 * 1024 * 1024:
                raise RuntimeError("Ollama canary model manifest is too large")
            return hashlib.sha256(payload).hexdigest()
        except Exception:
            self.remove(model_ref)
            raise

    def remove(self, model_ref: str) -> None:
        if not self._installed(model_ref):
            return
        removed = subprocess.run(
            (str(self._ollama), "rm", model_ref), check=False,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=60, env=self._environment(),
        )
        if removed.returncode != 0:
            raise RuntimeError("Ollama specialist model removal failed")
        if self._installed(model_ref):
            raise RuntimeError("Ollama specialist model remains after removal")

    def _installed(self, model_ref: str) -> bool:
        document = self._transport.request(
            "GET", f"{self._base_url}/api/tags", None, 60,
        )
        models = document.get("models")
        if not isinstance(models, list):
            raise RuntimeError("Ollama installed model catalog is invalid")
        names: list[str] = []
        for item in models:
            if not isinstance(item, dict):
                raise RuntimeError("Ollama installed model entry is invalid")
            name = item.get("name", item.get("model"))
            if not isinstance(name, str) or not name:
                raise RuntimeError("Ollama installed model identity is invalid")
            names.append(name)
        return model_ref in names

    def _environment(self) -> dict[str, str]:
        return {
            "HOME": str(Path.home()),
            "OLLAMA_HOST": self._base_url,
            "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        }
