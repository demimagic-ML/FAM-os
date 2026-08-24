"""Separate ephemeral workspace for one held-out evaluator run."""

from __future__ import annotations

import hashlib
import os
import shutil
import stat
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Protocol

from fam_os.expert_factory import FactoryEvaluationApproval, SealedDatasetBlobReceipt


class EvaluationBlobReader(Protocol):
    def read(self, receipt: SealedDatasetBlobReceipt) -> bytes: ...


@dataclass(frozen=True, slots=True)
class PreparedEvaluationWorkspace:
    root: Path
    input_directory: Path
    output_directory: Path
    held_out_path: Path
    plaintext_bytes: int


class FactoryEvaluationWorkspace:
    def __init__(
        self, root: Path, blob_store: EvaluationBlobReader, owner_uid: int,
    ) -> None:
        self._root = root
        self._blob_store = blob_store
        self._owner_uid = owner_uid

    @contextmanager
    def materialize(
        self, *, approval: FactoryEvaluationApproval,
        held_out: SealedDatasetBlobReceipt,
    ) -> Iterator[PreparedEvaluationWorkspace]:
        if (
            held_out.dataset_id != approval.sealed_dataset_id
            or held_out.blob_id != approval.held_out_blob_id
            or held_out.plaintext_sha256 != approval.held_out_blob_sha256
            or held_out.partition.value != "held_out"
        ):
            raise ValueError("evaluation workspace held-out data does not match approval")
        root = self._root / approval.one_use_evaluation_id
        if root.exists() or root.is_symlink():
            raise FileExistsError("evaluation workspace already exists")
        input_directory = root / "input"
        output_directory = root / "output"
        input_directory.mkdir(parents=True, mode=0o700)
        output_directory.mkdir(mode=0o700)
        self._verify_directories(root, input_directory, output_directory)
        payload = self._blob_store.read(held_out)
        if hashlib.sha256(payload).hexdigest() != approval.held_out_blob_sha256:
            raise RuntimeError("decrypted held-out content changed")
        held_out_path = input_directory / "held-out.jsonl"
        _write_private_new(held_out_path, payload)
        prepared = PreparedEvaluationWorkspace(
            root, input_directory, output_directory, held_out_path, len(payload),
        )
        try:
            yield prepared
        finally:
            _discard_tree(root)

    def _verify_directories(self, *paths: Path) -> None:
        for path in (self._root, *paths):
            os.chmod(path, 0o700)
            metadata = path.stat(follow_symlinks=False)
            if (
                stat.S_ISLNK(metadata.st_mode)
                or not stat.S_ISDIR(metadata.st_mode)
                or metadata.st_uid != self._owner_uid
                or stat.S_IMODE(metadata.st_mode) != 0o700
            ):
                raise PermissionError("evaluation workspace ownership is invalid")


def _write_private_new(path: Path, payload: bytes) -> None:
    descriptor = os.open(
        path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600,
    )
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def _discard_tree(root: Path) -> None:
    if root.is_symlink():
        raise OSError("evaluation workspace became a symlink")
    shutil.rmtree(root)
    descriptor = os.open(root.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
