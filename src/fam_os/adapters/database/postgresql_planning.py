"""Deterministic planning for isolated natural PostgreSQL migrations."""

from __future__ import annotations

import hashlib
import re
import stat
from datetime import datetime
from pathlib import Path

from fam_os.adapters.filesystem.candidate_io import contained, read_regular
from fam_os.adapters.integration.natural_template_identity import (
    POSTGRESQL_IMAGE_REF,
    POSTGRESQL_IMAGE_SHA256,
)
from fam_os.core.engineering import (
    POSTGRESQL_CANDIDATE_DATABASE,
    POSTGRESQL_MIGRATION_ROLE,
    IntegrationNetworkMode,
    EngineeringResourceImpact,
    PostgreSQLIntegrationVerificationPlan,
    PostgreSQLMigrationAsset,
)


_POSTGRESQL = re.compile(r"\bpostgres(?:ql)?\b", re.I)
_MIGRATION = re.compile(r"\b(?:migration|migrate|schema)\b", re.I)
_META_COMMAND = re.compile(r"(?m)^\s*\\")
_DESTRUCTIVE = re.compile(r"\b(?:ALTER|DELETE|DROP|TRUNCATE|UPDATE)\b", re.I)
_FORBIDDEN_SQL = (
    re.compile(r"\b(?:CREATE|ALTER|DROP)\s+(?:ROLE|USER|DATABASE|TABLESPACE)\b", re.I),
    re.compile(r"\bALTER\s+SYSTEM\b", re.I),
    re.compile(r"\bSET\s+(?:SESSION\s+AUTHORIZATION|ROLE)\b", re.I),
    re.compile(r"\bRESET\s+(?:SESSION\s+AUTHORIZATION|ROLE)\b", re.I),
    re.compile(r"\bCOPY\b[\s\S]{0,4096}\bPROGRAM\b", re.I),
    re.compile(r"\bLOAD\s+['\"]", re.I),
)
_MAX_ASSET_BYTES = 4 * 1024 * 1024


class NaturalPostgreSQLVerificationPlanBuilder:
    """Bind reversible SQL assets to one fixed isolated service plan."""

    @staticmethod
    def requested(intent: str) -> bool:
        return bool(_POSTGRESQL.search(intent) and _MIGRATION.search(intent))

    def build(
        self,
        definition,
        candidate,
        entries,
        changed_paths,
        environment_plan,
        *,
        now: datetime,
    ) -> PostgreSQLIntegrationVerificationPlan | None:
        if not self.requested(definition.task.intent):
            return None
        self._admit(definition, candidate, environment_plan, now)
        service = _postgresql_service(environment_plan)
        pairs = _migration_pairs(entries, tuple(changed_paths))
        if not pairs:
            raise LookupError(
                "PostgreSQL migration intent requires a changed .up.sql/.down.sql pair"
            )
        if len(pairs) > 4:
            raise ValueError("PostgreSQL verification supports at most four migration pairs")
        root = Path(candidate.candidate_workspace)
        assets = []
        consumed = 0
        for order, (forward, rollback) in enumerate(pairs, 1):
            forward_raw = _checked_content(root, entries, forward)
            rollback_raw = _checked_content(root, entries, rollback)
            consumed += len(forward_raw) + len(rollback_raw)
            _validate_sql(forward_raw, forward)
            _validate_sql(rollback_raw, rollback)
            assets.append(PostgreSQLMigrationAsset(
                f"postgresql-migration-{order}-{_short(forward)}",
                order,
                forward,
                _sha(forward_raw),
                rollback,
                _sha(rollback_raw),
                _DESTRUCTIVE.search(forward_raw.decode("utf-8")) is not None,
            ))
        maximum = min(definition.task.max_changed_bytes, 16 * 1024 * 1024)
        if consumed <= 0 or consumed > maximum:
            raise ValueError("PostgreSQL migration inputs exceed their admitted byte bound")
        identity = _sha("|".join((
            definition.task.task_id,
            candidate.candidate_id,
            environment_plan.environment_id,
            environment_plan.approved_changeset_id,
            service.service_id,
            *(
                value
                for asset in assets
                for value in (asset.forward_sha256, asset.rollback_sha256)
            ),
        )).encode())[:32]
        return PostgreSQLIntegrationVerificationPlan(
            f"postgresql-verification-{identity}",
            definition.task.task_id,
            candidate.candidate_id,
            environment_plan.environment_id,
            service.service_id,
            environment_plan.approved_changeset_id,
            environment_plan.exact_host_id,
            service.secret_refs[0],
            POSTGRESQL_CANDIDATE_DATABASE,
            POSTGRESQL_MIGRATION_ROLE,
            tuple(assets),
            maximum,
            16 * 1024 * 1024,
            EngineeringResourceImpact(
                600,
                24 + 9 * len(assets),
                1,
                2 * len(assets) + 1,
                maximum + 16 * 1024 * 1024,
                0,
            ),
            True,
            True,
            False,
            now,
            min(definition.task.expires_at, environment_plan.expires_at),
        )

    @staticmethod
    def _admit(definition, candidate, environment_plan, now) -> None:
        root = Path(candidate.candidate_workspace)
        if (
            candidate.task_id != definition.task.task_id
            or environment_plan.task_id != definition.task.task_id
            or environment_plan.candidate_id != candidate.candidate_id
            or environment_plan.candidate_root != str(root)
            or environment_plan.network_mode is not IntegrationNetworkMode.ISOLATED
            or environment_plan.network_hosts
            or "sql" not in definition.task.toolchains
            or not now < environment_plan.expires_at
            or root.is_symlink()
            or not root.is_dir()
            or root.resolve() != root
        ):
            raise PermissionError(
                "PostgreSQL verification requires the exact isolated candidate plan"
            )


def _postgresql_service(environment_plan):
    services = tuple(
        item for item in environment_plan.services
        if item.image_ref == POSTGRESQL_IMAGE_REF
        and item.image_sha256 == POSTGRESQL_IMAGE_SHA256
    )
    if len(services) != 1 or len(services[0].secret_refs) != 1:
        raise PermissionError(
            "PostgreSQL verification requires one fixed secret-bound service"
        )
    return services[0]


def _migration_pairs(entries, changed_paths: tuple[str, ...]):
    files = {
        item.path: item
        for item in entries
        if getattr(item.kind, "value", None) == "file"
    }
    changed = set(changed_paths)
    pairs = []
    for forward in sorted(changed):
        rollback = _rollback_path(forward)
        if (
            rollback is not None
            and forward in files
            and rollback in files
            and rollback in changed
        ):
            pairs.append((forward, rollback))
    return tuple(pairs)


def _rollback_path(path: str) -> str | None:
    if path.endswith(".up.sql"):
        return path[:-7] + ".down.sql"
    if path.endswith("_up.sql"):
        return path[:-7] + "_down.sql"
    if path.endswith(".sql") and not path.endswith((".down.sql", "_down.sql")):
        return path[:-4] + "_down.sql"
    return None


def _checked_content(root: Path, entries, relative: str) -> bytes:
    entry = next(item for item in entries if item.path == relative)
    path = contained(root, relative)
    details = path.stat(follow_symlinks=False)
    if not stat.S_ISREG(details.st_mode) or details.st_nlink != 1:
        raise PermissionError("PostgreSQL migration input must be a single-link file")
    raw = read_regular(path, _MAX_ASSET_BYTES)
    if len(raw) != entry.size_bytes or _sha(raw) != entry.content_sha256:
        raise RuntimeError("PostgreSQL migration input changed after observation")
    return raw


def _validate_sql(raw: bytes, relative: str) -> None:
    if not raw or b"\0" in raw:
        raise ValueError(f"PostgreSQL migration {relative} is empty or binary")
    try:
        sql = raw.decode("utf-8", "strict")
    except UnicodeDecodeError as error:
        raise ValueError(f"PostgreSQL migration {relative} is not UTF-8") from error
    if _META_COMMAND.search(sql):
        raise PermissionError("PostgreSQL psql meta-commands are not candidate SQL")
    if any(pattern.search(sql) for pattern in _FORBIDDEN_SQL):
        raise PermissionError("PostgreSQL migration requests administrative SQL")


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _short(value: str) -> str:
    return _sha(value.encode())[:16]
