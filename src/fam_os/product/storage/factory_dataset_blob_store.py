"""Owner-private immutable encrypted files for sealed factory partitions."""

from __future__ import annotations

import hashlib
import os
import secrets
import stat
from datetime import datetime
from pathlib import Path

from fam_os.expert_factory import (
    DatasetPartition,
    SealedDatasetBlobReceipt,
    build_sealed_dataset_blob_receipt,
)
from fam_os.product.storage.cipher import CipherContext, ProductPayloadCipher


class FactoryDatasetBlobStore:
    def __init__(
        self, root: Path, cipher: ProductPayloadCipher, owner_id: str,
        owner_uid: int,
    ) -> None:
        self._root = root
        self._cipher = cipher
        self._owner_id = owner_id
        self._owner_uid = owner_uid

    def put(
        self, *, blob_id: str, dataset_id: str, partition: DatasetPartition,
        plaintext_sha256: str, payload: bytes, created_at: datetime,
    ) -> SealedDatasetBlobReceipt:
        if hashlib.sha256(payload).hexdigest() != plaintext_sha256:
            raise ValueError("dataset blob payload does not match the sealed partition")
        path, relative = self._path(blob_id)
        self._prepare_directory(path.parent)
        context = CipherContext(
            self._owner_id, "factory-dataset-blob", blob_id, partition.value,
        )
        encrypted = self._cipher.encrypt(context, payload).encode("ascii")
        created = self._write_once(path, encrypted)
        stored = encrypted if created else self._read_private(path)
        plaintext = self._cipher.decrypt(context, stored.decode("ascii"))
        if plaintext != payload:
            raise RuntimeError("dataset blob identity already stores different content")
        return build_sealed_dataset_blob_receipt(
            blob_id=blob_id, dataset_id=dataset_id, partition=partition,
            plaintext_sha256=plaintext_sha256,
            ciphertext_sha256=hashlib.sha256(stored).hexdigest(),
            plaintext_bytes=len(payload), ciphertext_bytes=len(stored),
            relative_path=relative, created_at=created_at,
        )

    def read(self, receipt: SealedDatasetBlobReceipt) -> bytes:
        path, relative = self._path(receipt.blob_id)
        if relative != receipt.relative_path:
            raise ValueError("dataset blob receipt path is not canonical")
        stored = self._read_private(path)
        if (
            len(stored) != receipt.ciphertext_bytes
            or hashlib.sha256(stored).hexdigest() != receipt.ciphertext_sha256
        ):
            raise RuntimeError("encrypted dataset blob was changed")
        context = CipherContext(
            self._owner_id, "factory-dataset-blob", receipt.blob_id,
            receipt.partition.value,
        )
        payload = self._cipher.decrypt(context, stored.decode("ascii"))
        if (
            len(payload) != receipt.plaintext_bytes
            or hashlib.sha256(payload).hexdigest() != receipt.plaintext_sha256
        ):
            raise RuntimeError("decrypted dataset blob does not match its receipt")
        return payload

    def remove_orphan(self, receipt: SealedDatasetBlobReceipt) -> None:
        path, relative = self._path(receipt.blob_id)
        if relative == receipt.relative_path:
            path.unlink(missing_ok=True)

    def _path(self, blob_id: str) -> tuple[Path, str]:
        if not blob_id.startswith("factory-dataset-blob-") or not blob_id.replace(
            "-", "",
        ).isalnum():
            raise ValueError("dataset blob identity is invalid")
        shard = hashlib.sha256(blob_id.encode()).hexdigest()[:2]
        relative = f"blobs/{shard}/{blob_id}.blob"
        return self._root / relative, relative

    def _prepare_directory(self, path: Path) -> None:
        self._root.mkdir(parents=True, exist_ok=True, mode=0o700)
        relative = path.relative_to(self._root)
        current = self._root
        for component in relative.parts:
            current = current / component
            if current.is_symlink():
                raise OSError("dataset blob path cannot be a symlink")
            current.mkdir(exist_ok=True, mode=0o700)
        current = self._root
        for component in ((), *[(item,) for item in relative.parts]):
            if component:
                current = current / component[0]
            metadata = current.stat(follow_symlinks=False)
            if stat.S_ISLNK(metadata.st_mode):
                raise OSError("dataset blob path cannot be a symlink")
            os.chmod(current, 0o700)
            if metadata.st_uid != self._owner_uid or not stat.S_ISDIR(metadata.st_mode):
                raise PermissionError("dataset blob directory has unsafe ownership")

    def _write_once(self, path: Path, payload: bytes) -> bool:
        temporary = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
        descriptor = os.open(
            temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600,
        )
        try:
            with os.fdopen(descriptor, "wb", closefd=True) as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temporary, path, follow_symlinks=False)
            except FileExistsError:
                return False
            finally:
                temporary.unlink(missing_ok=True)
            directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
            return True
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise

    def _read_private(self, path: Path) -> bytes:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            metadata = os.fstat(descriptor)
            if (
                not stat.S_ISREG(metadata.st_mode)
                or metadata.st_uid != self._owner_uid
                or stat.S_IMODE(metadata.st_mode) != 0o600
                or metadata.st_nlink != 1
            ):
                raise PermissionError("dataset blob file has unsafe ownership or mode")
            with os.fdopen(descriptor, "rb", closefd=False) as stream:
                return stream.read()
        finally:
            os.close(descriptor)
