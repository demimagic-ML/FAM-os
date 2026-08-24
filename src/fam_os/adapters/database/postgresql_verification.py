"""Candidate-only PostgreSQL migration lifecycle verification."""

from __future__ import annotations

import hashlib
import stat
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fam_os.adapters.database.postgresql_commands import (
    PostgreSQLContainerCommands,
)
from fam_os.adapters.database.postgresql_admission import (
    PermitBoundPostgreSQLControl,
    admit_postgresql_runtime,
)
from fam_os.adapters.database.postgresql_storage import (
    retain_encrypted_postgresql_backup,
)
from fam_os.adapters.filesystem.candidate_io import contained, read_regular
from fam_os.adapters.integration.docker_client import DockerCommandClient
from fam_os.core.engineering import (
    PostgreSQLIntegrationVerificationReceipt,
)


class PostgreSQLIntegrationVerificationAdapter:
    """Verify reversible migrations inside one admitted disposable runtime."""

    def __init__(
        self,
        protector,
        client: DockerCommandClient | None = None,
        clock: Callable[[], datetime] | None = None,
        identifier: Callable[[], str] | None = None,
    ) -> None:
        self._protector = protector
        self._client = client or DockerCommandClient(
            maximum_output_bytes=64 * 1024 * 1024,
        )
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._identifier = identifier or (lambda: str(uuid4()))

    def execute(
        self,
        plan,
        candidate_root: Path,
        environment_plan,
        environment_receipt,
        permit,
        control,
        authorization_decision_ids,
    ) -> PostgreSQLIntegrationVerificationReceipt:
        service_receipt = admit_postgresql_runtime(
            self._client,
            plan,
            candidate_root,
            environment_plan,
            environment_receipt,
            permit,
            control,
            self._clock(),
        )
        bound = PermitBoundPostgreSQLControl(
            control, permit, plan, self._clock,
        )
        commands = PostgreSQLContainerCommands(
            self._client, service_receipt.runtime_id, bound,
        )
        restored_plaintext = None
        context = f"fam-postgresql-backup:{plan.plan_id}:{plan.environment_id}"
        try:
            commands.setup()
            baseline_schema, baseline_data = commands.digest(plan.database_name)
            plaintext = commands.backup()
            if not plaintext or len(plaintext) > plan.maximum_backup_bytes:
                raise ValueError("PostgreSQL baseline backup exceeds its bound")
            backup_identity = f"{plan.plan_id}:{self._identifier()}"
            backup_path, ciphertext = retain_encrypted_postgresql_backup(
                candidate_root,
                plaintext,
                self._protector,
                context,
                backup_identity,
                plan.maximum_backup_bytes,
            )
            restored_plaintext = self._protector.decrypt(ciphertext, context)
            if restored_plaintext != plaintext:
                raise RuntimeError("PostgreSQL encrypted backup did not round-trip")
            transfers = self._transfer_assets(plan, candidate_root)
            self._apply(commands, transfers, rollback=False)
            forward_schema, forward_data = commands.digest(plan.database_name)
            transaction_id = self._identifier()
            commands.transaction_probe(_token(transaction_id))
            transaction_schema, transaction_data = commands.digest(
                plan.database_name,
            )
            self._require_equal(
                (transaction_schema, transaction_data),
                (forward_schema, forward_data),
                "transaction rollback",
            )
            self._apply(commands, transfers, rollback=True)
            rollback_schema, rollback_data = commands.digest(plan.database_name)
            self._require_equal(
                (rollback_schema, rollback_data),
                (baseline_schema, baseline_data),
                "declared rollback",
            )
            self._apply(commands, transfers, rollback=False)
            reapplied_schema, reapplied_data = commands.digest(plan.database_name)
            self._require_equal(
                (reapplied_schema, reapplied_data),
                (forward_schema, forward_data),
                "deterministic reapplication",
            )
            commands.restore(restored_plaintext)
            restored_schema, restored_data = commands.digest("fam_restore")
            self._require_equal(
                (restored_schema, restored_data),
                (baseline_schema, baseline_data),
                "encrypted backup restore",
            )
            return PostgreSQLIntegrationVerificationReceipt(
                receipt_id=self._identifier(),
                plan_id=plan.plan_id,
                task_id=plan.task_id,
                candidate_id=plan.candidate_id,
                environment_id=plan.environment_id,
                service_id=plan.service_id,
                runtime_id=service_receipt.runtime_id,
                permit_id=permit.permit_id,
                authorization_decision_ids=tuple(authorization_decision_ids),
                backup_relative_path=backup_path.relative_to(candidate_root).as_posix(),
                backup_artifact_sha256=hashlib.sha256(ciphertext).hexdigest(),
                backup_size_bytes=len(ciphertext),
                backup_encrypted=True,
                baseline_schema_sha256=baseline_schema,
                baseline_data_sha256=baseline_data,
                forward_schema_sha256=forward_schema,
                forward_data_sha256=forward_data,
                transaction_schema_sha256=transaction_schema,
                transaction_data_sha256=transaction_data,
                rollback_schema_sha256=rollback_schema,
                rollback_data_sha256=rollback_data,
                reapplied_schema_sha256=reapplied_schema,
                reapplied_data_sha256=reapplied_data,
                restored_schema_sha256=restored_schema,
                restored_data_sha256=restored_data,
                applied_asset_ids=tuple(
                    item.asset_id for item in plan.migration_assets
                ),
                transaction_test_id=transaction_id,
                passed=True,
                completed_at=self._clock(),
                diagnostic=(
                    "isolated non-superuser migration, rollback, replay, "
                    "transaction, and encrypted restore passed"
                ),
            )
        except BaseException as execution_error:
            if restored_plaintext is not None:
                try:
                    commands.recover_candidate(restored_plaintext)
                except BaseException as recovery_error:
                    raise RuntimeError(
                        "PostgreSQL verification failed and baseline recovery is incomplete"
                    ) from recovery_error
            raise execution_error
        finally:
            commands.cleanup()

    def _transfer_assets(self, plan, root):
        transfers = []
        consumed = 0
        for asset in plan.migration_assets:
            forward = self._content(
                root, asset.forward_path, asset.forward_sha256,
                plan.maximum_input_bytes,
            )
            rollback = self._content(
                root, asset.rollback_path, asset.rollback_sha256,
                plan.maximum_input_bytes,
            )
            consumed += len(forward) + len(rollback)
            if consumed > plan.maximum_input_bytes:
                raise ValueError("PostgreSQL verification inputs exceed their bound")
            transfers.append((asset, forward, rollback))
        return tuple(transfers)

    @staticmethod
    def _apply(commands, transfers, *, rollback):
        ordered = reversed(transfers) if rollback else transfers
        for _asset, forward, down in ordered:
            commands.apply(down if rollback else forward)

    @staticmethod
    def _content(root, relative, expected, maximum):
        path = contained(root, relative)
        details = path.stat(follow_symlinks=False)
        if not stat.S_ISREG(details.st_mode) or details.st_nlink != 1:
            raise PermissionError("PostgreSQL input is not a single-link file")
        raw = read_regular(path, maximum)
        if hashlib.sha256(raw).hexdigest() != expected:
            raise RuntimeError("PostgreSQL input digest changed after planning")
        return raw

    @staticmethod
    def _require_equal(observed, expected, action):
        if observed != expected:
            raise RuntimeError(f"PostgreSQL {action} did not match its exact state")


def _token(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:20]
