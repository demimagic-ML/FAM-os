"""Restart-cleanable file-only secrets for process integration services."""

import hashlib
import os
from pathlib import Path
import re
import shutil

from fam_os.adapters.integration.secret_consumer import (
    integration_secret_consumer_id,
)


_SAFE_KEY = re.compile(r"[A-Z][A-Z0-9_]{0,63}\Z")
_DENIED_KEYS = frozenset({"HOME", "PATH", "LD_PRELOAD", "PYTHONPATH"})


class DenyingProcessSecretProvider:
    def environment(self, secret_refs, consumer_id):
        if secret_refs:
            raise PermissionError("process credentials are not provisioned")
        return {}


class ProcessSecretFiles:
    def __init__(self, provider=None) -> None:
        self._provider = provider or DenyingProcessSecretProvider()

    def materialize(self, root: Path, environment_id: str, service):
        values = dict(self._provider.environment(
            service.secret_refs,
            integration_secret_consumer_id(service),
        ))
        if service.secret_refs and not values:
            raise PermissionError("process secret provider returned no values")
        self._validate(values)
        if not values:
            return (), None
        parent = self._private_parent(root)
        identity = hashlib.sha256(
            f"{environment_id}:{service.service_id}".encode(),
        ).hexdigest()[:24]
        secret_root = parent / f"process-{identity}"
        secret_root.mkdir(mode=0o700)
        try:
            arguments = self._write_values(secret_root, values)
        except BaseException:
            shutil.rmtree(secret_root)
            raise
        return arguments, str(secret_root.relative_to(root))

    def cleanup(self, root: Path, relative_roots) -> tuple[str, ...]:
        evidence = []
        for relative in reversed(tuple(relative_roots)):
            path = root / relative
            if (
                Path(relative).parts[:2] != (".fam", "secret-injection")
                or len(Path(relative).parts) != 3
                or not Path(relative).name.startswith("process-")
                or path.is_symlink()
            ):
                raise PermissionError("process secret root identity is invalid")
            if path.exists():
                details = path.stat(follow_symlinks=False)
                if details.st_uid != os.geteuid() or details.st_mode & 0o077:
                    raise PermissionError("process secret root ownership is invalid")
                shutil.rmtree(path)
            evidence.append(f"removed-secret-root:{relative}")
        return tuple(evidence)

    @staticmethod
    def _validate(values) -> None:
        if any(
            key in _DENIED_KEYS or key.endswith("_FILE")
            or not _SAFE_KEY.fullmatch(key)
            or not isinstance(value, str) or "\0" in value
            or len(value.encode()) > 65_536
            for key, value in values.items()
        ):
            raise PermissionError("process secret injection is invalid")

    @staticmethod
    def _private_parent(root: Path) -> Path:
        parent = root / ".fam" / "secret-injection"
        current = parent
        missing = []
        while not current.exists():
            missing.append(current)
            current = current.parent
        if current.is_symlink():
            raise PermissionError("process secret root traverses a symbolic link")
        for path in reversed(missing):
            path.mkdir(mode=0o700)
        if parent.is_symlink():
            raise PermissionError("process secret root is symbolic")
        return parent

    @staticmethod
    def _write_values(root: Path, values) -> tuple[str, ...]:
        arguments = []
        for key in sorted(values):
            path = root / key
            descriptor = os.open(
                path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
            )
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write(values[key])
                stream.flush()
                os.fsync(stream.fileno())
            target = f"/run/fam-secrets/{key}"
            arguments.extend(("--ro-bind", str(path), target, "--setenv", f"{key}_FILE", target))
        return tuple(arguments)
