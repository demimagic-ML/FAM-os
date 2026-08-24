"""Build and identify immutable Python release artifacts."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path


def build_wheel(
    repository: Path, python: Path, output: Path, log_path: Path,
) -> Path:
    output.mkdir(parents=True, exist_ok=False)
    with log_path.open("w", encoding="utf-8") as log:
        subprocess.run(
            (
                str(python), "-m", "pip", "wheel", str(repository),
                "--no-deps", "--wheel-dir", str(output),
            ),
            cwd=repository, check=True, stdout=log, stderr=subprocess.STDOUT,
            text=True, timeout=600,
        )
    wheels = tuple(output.glob("fam_os-*.whl"))
    if len(wheels) != 1 or wheels[0].is_symlink():
        raise RuntimeError("release build did not produce exactly one safe FAM_OS wheel")
    return wheels[0]


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

