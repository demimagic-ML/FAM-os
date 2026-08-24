"""Probe an exact offline llama.cpp conversion environment."""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

from fam_os.expert_factory import FactoryConversionEnvironment, build_conversion_environment


_PACKAGES = ("numpy", "protobuf", "sentencepiece", "torch", "transformers")


class LlamaCppConversionEnvironmentProbe:
    def __init__(
        self, *, environment_directory: Path, wheelhouse_manifest: Path,
        llama_cpp_directory: Path, expected_revision: str, ollama: Path,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._environment = environment_directory
        self._wheelhouse = wheelhouse_manifest
        self._llama = llama_cpp_directory
        self._revision = expected_revision
        self._ollama = ollama
        self._now = now or (lambda: datetime.now(UTC))

    def probe(self) -> FactoryConversionEnvironment:
        revision = subprocess.run(
            ("git", "-C", str(self._llama), "rev-parse", "HEAD"),
            check=True, capture_output=True, text=True, timeout=30,
        ).stdout.strip()
        if revision != self._revision:
            raise PermissionError("llama.cpp revision changed")
        dirty = subprocess.run(
            ("git", "-C", str(self._llama), "status", "--porcelain"),
            check=True, capture_output=True, text=True, timeout=30,
        ).stdout
        if dirty:
            raise PermissionError("llama.cpp conversion source is modified")
        manifest = json.loads(self._wheelhouse.read_text("utf-8"))
        wheelhouse_sha = manifest.get("manifest_sha256")
        if not isinstance(wheelhouse_sha, str) or len(wheelhouse_sha) != 64:
            raise ValueError("conversion wheelhouse manifest is invalid")
        canonical = {name: value for name, value in manifest.items() if name != "manifest_sha256"}
        if hashlib.sha256(json.dumps(
            canonical, sort_keys=True, separators=(",", ":"),
        ).encode()).hexdigest() != wheelhouse_sha:
            raise ValueError("conversion wheelhouse digest does not match")
        python = self._environment.absolute() / "bin/python"
        if not python.exists():
            raise FileNotFoundError("conversion environment Python is unavailable")
        packages = _package_versions(python)
        output = subprocess.run(
            (str(self._ollama), "--version"), check=True,
            capture_output=True, text=True, timeout=30,
        ).stdout.strip()
        return build_conversion_environment(
            environment_id="llama-cpp-qwen3-conversion-v1",
            llama_cpp_revision=revision,
            convert_hf_script_sha256=_sha(self._llama / "convert_hf_to_gguf.py"),
            convert_lora_script_sha256=_sha(
                self._llama / "convert_lora_to_gguf.py",
            ),
            wheelhouse_manifest_sha256=wheelhouse_sha,
            python_executable_sha256=_sha(python), package_versions=packages,
            ollama_version=output, observed_at=self._now(),
        )


def _package_versions(python: Path) -> tuple[tuple[str, str], ...]:
    script = (
        "import importlib.metadata,json;"
        f"print(json.dumps({{x:importlib.metadata.version(x) for x in {_PACKAGES!r}}},sort_keys=True))"
    )
    output = subprocess.run(
        (str(python), "-I", "-c", script), check=True,
        capture_output=True, text=True, timeout=60,
    ).stdout
    document = json.loads(output)
    if not isinstance(document, dict):
        raise RuntimeError("conversion package probe is invalid")
    return tuple(sorted((str(name), str(version)) for name, version in document.items()))


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
