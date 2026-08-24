"""Private, bounded artifact creation inside an owner-selected workspace."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from uuid import uuid4

from fam_os.product.useful_tasks.contracts import UsefulArtifact


class UsefulArtifactWriter:
    def __init__(self, workspace_root: Path, task_id: str) -> None:
        root = workspace_root.resolve(strict=True)
        if not root.is_dir():
            raise ValueError("workspace root must be a directory")
        self._root = root
        self._task_id = task_id
        self._output = root / ".fam-output" / task_id
        self._output.mkdir(parents=True, exist_ok=False, mode=0o700)

    @property
    def output_root(self) -> Path:
        return self._output

    def write_text(
        self, name: str, content: str, *, kind: str, media_type: str,
    ) -> UsefulArtifact:
        if Path(name).name != name or name in {".", ".."}:
            raise ValueError("artifact name must be a plain filename")
        encoded = content.encode("utf-8")
        if len(encoded) > 8_388_608:
            raise ValueError("artifact exceeds the useful-workflow limit")
        path = self._output / name
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        return UsefulArtifact(
            f"artifact-{uuid4()}", self._task_id, kind, path, media_type,
            hashlib.sha256(encoded).hexdigest(), len(encoded),
        )


def selected_paths(
    workspace_root: Path, values: object, suffixes: tuple[str, ...],
) -> tuple[Path, ...]:
    root = workspace_root.resolve(strict=True)
    if values is None:
        candidates = sorted(
            item for item in root.rglob("*")
            if item.is_file() and item.suffix.casefold() in suffixes
            and ".fam-output" not in item.parts
        )
    else:
        if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
            raise ValueError("input_paths must be a list of paths")
        candidates = [Path(item) if Path(item).is_absolute() else root / item for item in values]
    selected = []
    for candidate in candidates:
        resolved = candidate.resolve(strict=True)
        if not resolved.is_relative_to(root) or not resolved.is_file():
            raise PermissionError("workflow input must be a regular file inside the workspace")
        if resolved.suffix.casefold() not in suffixes:
            raise ValueError(f"unsupported input type: {resolved.suffix}")
        selected.append(resolved)
    if not selected:
        raise ValueError("no matching input files were found")
    return tuple(selected)
