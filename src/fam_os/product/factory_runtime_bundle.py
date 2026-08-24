"""Safe extraction of the runtime-only members from a specialist package."""

from __future__ import annotations

import os
import shutil
import tarfile
from pathlib import Path


def factory_package_artifact(root: Path, locator: str) -> Path:
    relative = Path(locator)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("factory package locator is unsafe")
    path = root / relative
    if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(
        root.resolve(),
    ):
        raise FileNotFoundError("installed factory package is unavailable")
    return path


def extract_factory_runtime_bundle(artifact: Path, destination: Path) -> None:
    destination.mkdir(mode=0o700)
    expected = {
        "runtime/base.gguf": "base.gguf",
        "runtime/adapter.gguf": "adapter.gguf",
        "runtime/Modelfile": "Modelfile",
    }
    with tarfile.open(artifact, "r:") as archive:
        members = {item.name: item for item in archive.getmembers()}
        if not set(expected).issubset(members) or any(
            not members[name].isfile() or members[name].issym()
            or members[name].islnk() for name in expected
        ):
            raise ValueError("factory runtime bundle members are invalid")
        for archive_name, target_name in expected.items():
            stream = archive.extractfile(members[archive_name])
            if stream is None:
                raise ValueError("factory runtime bundle is unreadable")
            target = destination / target_name
            descriptor = os.open(
                target, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW,
                0o600,
            )
            with stream, os.fdopen(descriptor, "wb") as output:
                shutil.copyfileobj(stream, output, length=1024 * 1024)
