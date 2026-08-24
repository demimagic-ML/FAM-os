"""Validation helpers for the bounded Docker environment adapter."""

import hashlib
from pathlib import Path

from fam_os.core.engineering.integration_environment import IntegrationEnvironmentPlan


def required_output(result, action: str) -> str:
    if result.exit_code != 0:
        raise RuntimeError(f"{action} failed")
    try:
        value = result.output.decode("utf-8", "strict").strip()
    except UnicodeDecodeError as error:
        raise RuntimeError(f"{action} returned non-UTF-8 output") from error
    if not value or "\n" in value:
        raise RuntimeError(f"{action} returned invalid output")
    return value


def runtime_name(kind: str, identity: str) -> str:
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:20]
    return f"fam-{kind}-{digest}"


def confined_path(root: Path, relative: str) -> Path:
    path = root / relative
    current = root
    for part in Path(relative).parts:
        current = current / part
        if current.exists() and current.is_symlink():
            raise PermissionError("Docker volume path traverses a symlink")
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=True))
    except ValueError as error:
        raise PermissionError("Docker volume escapes candidate root") from error
    return path


def directory_size(path: Path) -> int:
    total = 0
    for item in path.rglob("*"):
        if item.is_symlink():
            raise PermissionError("Docker volume contains a symlink")
        if item.is_file():
            total += item.stat(follow_symlinks=False).st_size
    return total


def ordered_services(plan: IntegrationEnvironmentPlan):
    remaining = {item.service_id: item for item in plan.services}
    emitted = set()
    while remaining:
        ready = sorted(
            (
                item for item in remaining.values()
                if set(item.dependency_ids) <= emitted
            ),
            key=lambda item: item.service_id,
        )
        if not ready:
            raise ValueError("Docker service dependency order is invalid")
        for item in ready:
            remaining.pop(item.service_id)
            emitted.add(item.service_id)
            yield item
