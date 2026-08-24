"""Materialize only approved train/validation data for one consumed job."""

from __future__ import annotations

import hashlib
import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from fam_os.expert_factory import (
    DatasetPartition,
    FactoryTrainingApproval,
    SealedDatasetBlobReceipt,
    SealedFactoryDataset,
)


@dataclass(frozen=True, slots=True)
class PreparedTrainingWorkspace:
    root: Path
    input_directory: Path
    output_directory: Path
    config_path: Path
    train_path: Path
    validation_path: Path


class DatasetBlobReader(Protocol):
    def read(self, receipt: SealedDatasetBlobReceipt) -> bytes: ...


class FactoryTrainingWorkspace:
    def __init__(
        self, root: Path, blob_store: DatasetBlobReader, owner_uid: int,
    ) -> None:
        self._root = root
        self._blob_store = blob_store
        self._owner_uid = owner_uid

    def prepare(
        self, *, approval: FactoryTrainingApproval, dataset: SealedFactoryDataset,
        blobs: tuple[SealedDatasetBlobReceipt, ...], model_directory: Path,
    ) -> PreparedTrainingWorkspace:
        if dataset.dataset_id != approval.sealed_dataset_id or (
            dataset.manifest_sha256 != approval.sealed_dataset_sha256
        ):
            raise ValueError("training workspace dataset does not match approval")
        if model_files_manifest_sha256(model_directory) != (
            approval.base_model.files_manifest_sha256
        ):
            raise ValueError("training workspace model does not match approval")
        by_partition = {item.partition: item for item in blobs}
        if set(by_partition) != set(DatasetPartition):
            raise ValueError("training workspace dataset blobs are incomplete")
        root = self._root / approval.one_use_job_id
        if root.exists() or root.is_symlink():
            raise FileExistsError("training workspace already exists")
        input_directory = root / "input"
        output_directory = root / "output"
        input_directory.mkdir(parents=True, mode=0o700)
        output_directory.mkdir(mode=0o700)
        for path in (self._root, root, input_directory, output_directory):
            os.chmod(path, 0o700)
            metadata = path.stat(follow_symlinks=False)
            if metadata.st_uid != self._owner_uid or not stat.S_ISDIR(metadata.st_mode):
                raise PermissionError("training workspace ownership is invalid")
        train = input_directory / "train.jsonl"
        validation = input_directory / "validation.jsonl"
        _write_private_new(
            train, self._blob_store.read(by_partition[DatasetPartition.TRAIN]),
        )
        _write_private_new(
            validation,
            self._blob_store.read(by_partition[DatasetPartition.VALIDATION]),
        )
        config = input_directory / "config.json"
        _write_private_new(config, _config_document(
            approval, train, validation, model_directory,
        ))
        return PreparedTrainingWorkspace(
            root, input_directory, output_directory, config, train, validation,
        )


def model_files_manifest_sha256(path: Path) -> str:
    if not path.is_dir() or path.is_symlink():
        raise ValueError("base model directory is invalid")
    records = []
    for item in sorted(path.rglob("*")):
        if item.is_symlink():
            raise ValueError("base model directory cannot contain symlinks")
        if item.is_file():
            records.append((item.relative_to(path).as_posix(), _file_sha256(item)))
    if not records:
        raise ValueError("base model directory is empty")
    return hashlib.sha256(
        json.dumps(records, separators=(",", ":")).encode(),
    ).hexdigest()


def _config_document(
    approval: FactoryTrainingApproval, train: Path, validation: Path,
    model_directory: Path,
) -> bytes:
    recipe = approval.recipe
    document = {
        "alpha": recipe.alpha,
        "base_model_directory": "/model",
        "base_model_sha256": approval.base_model.files_manifest_sha256,
        "compute_dtype": recipe.compute_dtype.value,
        "dropout": recipe.dropout, "epochs": recipe.epochs,
        "gradient_accumulation_steps": recipe.gradient_accumulation_steps,
        "learning_rate": recipe.learning_rate,
        "maximum_sequence_tokens": recipe.maximum_sequence_tokens,
        "maximum_steps": recipe.maximum_steps,
        "output_directory": "/output",
        "per_device_batch_size": recipe.per_device_batch_size,
        "rank": recipe.rank,
        "record_format": "qwen_chat_prompt_completion_v1",
        "seed": recipe.seed,
        "target_modules": list(recipe.target_modules),
        "train_dataset": "/input/train.jsonl",
        "train_sha256": _file_sha256(train),
        "validation_dataset": "/input/validation.jsonl",
        "validation_sha256": _file_sha256(validation),
    }
    return (json.dumps(document, indent=2, sort_keys=True) + "\n").encode()


def _write_private_new(path: Path, payload: bytes) -> None:
    descriptor = os.open(
        path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600,
    )
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
