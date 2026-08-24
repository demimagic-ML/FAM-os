"""Owner-private installed configuration for the complete Expert Factory runtime."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path


FACTORY_RUNTIME_CONFIGURATION_VERSION = "fam.product.factory-runtime/v1alpha1"


@dataclass(frozen=True, slots=True)
class FactoryRuntimeConfiguration:
    training_environment_directory: str
    training_wheelhouse_manifest: str
    training_model_directory: str
    evaluation_suite: str
    conversion_environment_directory: str
    conversion_wheelhouse_manifest: str
    llama_cpp_directory: str
    llama_cpp_revision: str
    conversion_model_directory: str
    canary_suite: str
    allowed_licenses: tuple[str, ...]
    contract_version: str = FACTORY_RUNTIME_CONFIGURATION_VERSION

    def __post_init__(self) -> None:
        directories = (
            self.training_environment_directory,
            self.training_model_directory,
            self.conversion_environment_directory,
            self.llama_cpp_directory,
            self.conversion_model_directory,
        )
        files = (
            self.training_wheelhouse_manifest,
            self.evaluation_suite,
            self.conversion_wheelhouse_manifest,
            self.canary_suite,
        )
        for value in (*directories, *files):
            if not Path(value).is_absolute():
                raise ValueError("factory runtime paths must be absolute")
        if len(self.llama_cpp_revision) != 40 or any(
            character not in "0123456789abcdef"
            for character in self.llama_cpp_revision
        ):
            raise ValueError("factory runtime llama.cpp revision is invalid")
        if not self.allowed_licenses or any(
            not value.strip() for value in self.allowed_licenses
        ):
            raise ValueError("factory runtime licenses are invalid")
        if self.contract_version != FACTORY_RUNTIME_CONFIGURATION_VERSION:
            raise ValueError("unsupported factory runtime configuration")

    def validate_sources(self) -> None:
        for value in (
            self.training_environment_directory,
            self.training_model_directory,
            self.conversion_environment_directory,
            self.llama_cpp_directory,
            self.conversion_model_directory,
        ):
            path = Path(value)
            if not path.is_dir() or path.is_symlink():
                raise ValueError("factory runtime directory is unavailable or unsafe")
        for value in (
            self.training_wheelhouse_manifest,
            self.evaluation_suite,
            self.conversion_wheelhouse_manifest,
            self.canary_suite,
        ):
            path = Path(value)
            if not path.is_file() or path.is_symlink():
                raise ValueError("factory runtime file is unavailable or unsafe")


class FactoryRuntimeConfigurationStore:
    def __init__(self, path: Path, owner_uid: int) -> None:
        self._path = path
        self._owner_uid = owner_uid

    def load(self) -> FactoryRuntimeConfiguration | None:
        if not self._path.exists():
            return None
        self._validate_file()
        document = json.loads(self._path.read_text("utf-8"))
        if not isinstance(document, dict):
            raise ValueError("factory runtime configuration must be an object")
        licenses = document.get("allowed_licenses")
        if not isinstance(licenses, list):
            raise ValueError("factory runtime licenses must be a list")
        document["allowed_licenses"] = tuple(licenses)
        configuration = FactoryRuntimeConfiguration(**document)
        configuration.validate_sources()
        return configuration

    def save(
        self, configuration: FactoryRuntimeConfiguration,
    ) -> FactoryRuntimeConfiguration:
        configuration.validate_sources()
        self._path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        os.chmod(self._path.parent, 0o700)
        if self._path.parent.stat().st_uid != self._owner_uid:
            raise PermissionError("factory runtime configuration owner is unsafe")
        temporary = self._path.with_suffix(".tmp")
        descriptor = os.open(
            temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW,
            0o600,
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(asdict(configuration), stream, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self._path)
        finally:
            temporary.unlink(missing_ok=True)
        self._validate_file()
        return configuration

    def remove(self) -> bool:
        if not self._path.exists():
            return False
        self._validate_file()
        self._path.unlink()
        return True

    def _validate_file(self) -> None:
        if (
            not self._path.is_file()
            or self._path.is_symlink()
            or self._path.stat().st_uid != self._owner_uid
            or self._path.stat().st_mode & 0o077
        ):
            raise PermissionError("factory runtime configuration is unsafe")
