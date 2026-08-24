"""Probe the exact NVIDIA QLoRA Python environment in a child process."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from fam_os.expert_factory import TrainingBackendEnvironment, build_training_environment


_PACKAGES = (
    "accelerate", "bitsandbytes", "datasets", "peft", "torch", "transformers", "trl",
)
_PROBE = r"""
import importlib.metadata
import json
import platform

versions = {}
reasons = []
for name in %r:
    try:
        versions[name] = importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        reasons.append("package.missing:" + name)
try:
    import torch
    cuda = bool(torch.cuda.is_available())
    if cuda:
        index = torch.cuda.current_device()
        properties = torch.cuda.get_device_properties(index)
        capability = torch.cuda.get_device_capability(index)
        device = {
            "index": index,
            "name": properties.name,
            "compute_capability": "%%d.%%d" %% capability,
            "total_vram_bytes": properties.total_memory,
            "bfloat16_supported": bool(torch.cuda.is_bf16_supported()),
        }
    else:
        reasons.append("torch.cuda_unavailable")
        device = None
    torch_cuda = str(torch.version.cuda or "unavailable")
except Exception as error:
    reasons.append("torch.probe_failed:" + type(error).__name__)
    cuda = False
    device = None
    torch_cuda = "unavailable"
try:
    import bitsandbytes.cextension as extension
    library = getattr(extension, "lib", None)
    bnb_cuda = bool(library and getattr(library, "compiled_with_cuda", False))
    if not bnb_cuda:
        reasons.append("bitsandbytes.cuda_unavailable")
except Exception as error:
    bnb_cuda = False
    reasons.append("bitsandbytes.probe_failed:" + type(error).__name__)
print(json.dumps({
    "python_version": platform.python_version(),
    "platform": platform.platform(),
    "versions": versions,
    "reasons": sorted(set(reasons)),
    "cuda_available": cuda,
    "bitsandbytes_cuda_available": bnb_cuda,
    "torch_cuda_version": torch_cuda,
    "device": device,
}, sort_keys=True))
""" % (_PACKAGES,)


class NvidiaQloraEnvironmentProbe:
    def __init__(
        self, python: Path, wheelhouse_manifest: Path, worker_script: Path,
        now: Callable[[], datetime] | None = None, timeout_seconds: int = 60,
    ) -> None:
        self._python = python
        self._manifest = wheelhouse_manifest
        self._worker_script = worker_script
        self._now = now or (lambda: datetime.now(UTC))
        self._timeout = timeout_seconds

    def probe(self) -> TrainingBackendEnvironment:
        wheel_manifest = json.loads(self._manifest.read_text("utf-8"))
        manifest_sha256 = wheel_manifest.get("manifest_sha256")
        if not isinstance(manifest_sha256, str):
            raise ValueError("training wheelhouse manifest has no digest")
        canonical = {
            key: value for key, value in wheel_manifest.items()
            if key != "manifest_sha256"
        }
        if hashlib.sha256(json.dumps(
            canonical, sort_keys=True, separators=(",", ":"),
        ).encode()).hexdigest() != manifest_sha256:
            raise ValueError("training wheelhouse manifest digest does not match")
        result = subprocess.run(
            (str(self._python), "-I", "-c", _PROBE),
            check=False, capture_output=True, text=True, timeout=self._timeout,
            env={
                "CUDA_VISIBLE_DEVICES": "0", "HOME": "/nonexistent",
                "PATH": "/usr/bin:/bin", "PYTHONHASHSEED": "0",
            },
        )
        if result.returncode != 0:
            raise RuntimeError("training environment probe failed")
        document = json.loads(result.stdout)
        device = document.get("device")
        if not isinstance(device, dict):
            raise RuntimeError("training environment has no usable NVIDIA GPU")
        versions = document.get("versions")
        if not isinstance(versions, dict):
            raise RuntimeError("training environment package probe is invalid")
        reasons = tuple(document.get("reasons", ()))
        if any(not isinstance(item, str) for item in reasons):
            raise RuntimeError("training environment reasons are invalid")
        return build_training_environment(
            environment_id="nvidia-qwen3-1.7b-qlora-v1",
            python_version=_text(document, "python_version"),
            python_executable_sha256=_file_sha256(self._python.resolve()),
            platform=_text(document, "platform"),
            package_versions=tuple(sorted(
                (name, str(versions[name])) for name in _PACKAGES if name in versions
            )),
            wheelhouse_manifest_sha256=manifest_sha256,
            worker_script_sha256=_file_sha256(self._worker_script),
            torch_cuda_version=str(document["torch_cuda_version"]),
            nvidia_driver_version=_driver_version(),
            device_index=_integer(device, "index"),
            device_name=_text(device, "name"),
            compute_capability=_text(device, "compute_capability"),
            total_vram_bytes=_integer(device, "total_vram_bytes"),
            cuda_available=document.get("cuda_available") is True,
            bfloat16_supported=device.get("bfloat16_supported") is True,
            bitsandbytes_cuda_available=(
                document.get("bitsandbytes_cuda_available") is True
            ),
            incompatibility_reasons=reasons,
            observed_at=self._now(),
        )


def _driver_version() -> str:
    result = subprocess.run(
        ("nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"),
        check=False, capture_output=True, text=True, timeout=10,
        env={"PATH": os.environ.get("PATH", "/usr/bin:/bin")},
    )
    value = result.stdout.splitlines()[0].strip() if result.returncode == 0 else ""
    if not value:
        raise RuntimeError("NVIDIA driver version is unavailable")
    return value


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _text(document: dict[str, Any], name: str) -> str:
    value = document.get(name)
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"training environment {name} is invalid")
    return value


def _integer(document: dict[str, Any], name: str) -> int:
    value = document.get(name)
    if not isinstance(value, int) or isinstance(value, bool):
        raise RuntimeError(f"training environment {name} is invalid")
    return value
