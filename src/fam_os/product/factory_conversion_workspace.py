"""Owner-private durable workspace for approved conversion outputs."""

from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path

from fam_os.expert_factory import FactoryConversionApproval


@dataclass(frozen=True, slots=True)
class PreparedConversionWorkspace:
    root: Path
    input_directory: Path
    output_directory: Path
    config_path: Path


class FactoryConversionWorkspace:
    def __init__(self, root: Path, owner_uid: int) -> None:
        self._root = root
        self._owner_uid = owner_uid

    def prepare(
        self, approval: FactoryConversionApproval,
    ) -> PreparedConversionWorkspace:
        root = self._root / approval.one_use_conversion_id
        if root.exists() or root.is_symlink():
            raise FileExistsError("conversion workspace already exists")
        input_directory = root / "input"
        output_directory = root / "output"
        input_directory.mkdir(parents=True, mode=0o700)
        output_directory.mkdir(mode=0o700)
        for path in (self._root, root, input_directory, output_directory):
            os.chmod(path, 0o700)
            metadata = path.stat(follow_symlinks=False)
            if (
                stat.S_ISLNK(metadata.st_mode)
                or not stat.S_ISDIR(metadata.st_mode)
                or metadata.st_uid != self._owner_uid
                or stat.S_IMODE(metadata.st_mode) != 0o700
            ):
                raise PermissionError("conversion workspace ownership is invalid")
        config_path = input_directory / "config.json"
        document = {
            "adapter_output_type": approval.adapter_output_type.value,
            "base_output_type": approval.base_output_type.value,
            "maximum_output_bytes": approval.maximum_output_bytes,
            "runtime_model_ref": approval.runtime_model_ref,
        }
        _write_private_new(
            config_path,
            (json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n").encode(),
        )
        return PreparedConversionWorkspace(
            root, input_directory, output_directory, config_path,
        )


def _write_private_new(path: Path, payload: bytes) -> None:
    descriptor = os.open(
        path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600,
    )
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
