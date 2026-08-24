"""Owner-scoped candidate database engineering in the master lifecycle."""

import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from fam_os.adapters.filesystem import CandidateWorkspaceAdapter
from fam_os.adapters.database.sqlite_digest import (
    sqlite_data_digest, sqlite_schema_digest,
)
from fam_os.adapters.database.sqlite_storage import secure_database_path
from fam_os.core.engineering import (
    DatabaseChangeStatus, DatabasePostapplyReceipt, EngineeringLoopStage,
)


class ProductDatabaseEngineeringApi:
    def __init__(
        self, owner_id, tasks, preparations, candidate_root: Path,
        builder, service, store, lifecycle, require_owner, validate_grant,
        *, clock=None,
    ) -> None:
        self._owner_id = owner_id
        self._tasks = tasks
        self._preparations = preparations
        self._candidate_root = candidate_root
        self._builder = builder
        self._service = service
        self._store = store
        self._lifecycle = lifecycle
        self._require_owner = require_owner
        self._validate_grant = validate_grant
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def requested(self, owner_id: str, task_id: str) -> bool:
        definition = self._definition(owner_id, task_id)
        return self._builder is not None and self._builder.requested(
            definition.task.intent
        )

    def execute_natural(
        self, owner_id: str, task_id: str, changed_paths,
        changeset_id: str, *, session_id: str, principal_id: str,
    ):
        definition = self._definition(owner_id, task_id)
        preparation = self._preparations.load(task_id)
        state = self._tasks.load(task_id)
        if preparation is None or state is None:
            raise KeyError("database engineering preparation is unavailable")
        if state.stage not in {
            EngineeringLoopStage.CANDIDATE_READY, EngineeringLoopStage.VERIFIED,
        }:
            raise PermissionError("database engineering lifecycle stage is invalid")
        self._validate_grant(task_id, definition.task.grant_id, self._clock())
        existing = self._store.plans_for_task(task_id) if self._store else ()
        if existing:
            if len(existing) != 1 or existing[0].approved_changeset_id != changeset_id:
                raise RuntimeError("database engineering recovery plan conflicts")
            result = self._store.load_result(existing[0].plan_id)
            if result is not None:
                if result.verification.status is DatabaseChangeStatus.VERIFIED:
                    self._record_verified(result)
                return result
            return self._reconcile(
                definition, preparation, existing[0], session_id, principal_id,
            )
        if self._builder is None or self._service is None or self._store is None:
            raise RuntimeError("installed database engineering was not composed")
        adapter = CandidateWorkspaceAdapter(
            Path(preparation.candidate.owner_workspace), self._candidate_root,
        )
        candidate = adapter.current_entries(preparation.candidate)
        plan = self._builder.build(
            definition, preparation.candidate, candidate, tuple(changed_paths),
            changeset_id, now=self._clock(),
        )
        if plan is None:
            return None
        self._store.put_plan(plan)
        try:
            result = self._service.execute(
                plan, preparation.candidate, definition.task.grant_id,
                principal_id, session_id, lambda: False,
            )
        except Exception:
            return self._reconcile(
                definition, preparation, plan, session_id, principal_id,
            )
        self._store.put_success(plan.plan_id, result)
        stored = self._store.load_result(plan.plan_id)
        self._record_verified(stored)
        return stored

    def plans_for_task(self, owner_id: str, task_id: str):
        self._definition(owner_id, task_id)
        return () if self._store is None else self._store.plans_for_task(task_id)

    def results_for_task(self, owner_id: str, task_id: str):
        self._definition(owner_id, task_id)
        return () if self._store is None else self._store.results_for_task(task_id)

    def reverify_postapply(
        self, owner_id: str, task_id: str, *, record_lifecycle: bool = True,
    ):
        definition = self._definition(owner_id, task_id)
        if self._store is None:
            return ()
        results = self._store.results_for_task(task_id)
        if not results:
            return ()
        prior = {
            item.plan_id: item
            for item in self._store.postapply_for_task(task_id)
        }
        values = []
        for result in results:
            receipt = prior.get(result.plan.plan_id)
            if receipt is None:
                receipt = self._observe_owner_database(definition, result)
                self._store.put_postapply(receipt)
            if receipt.passed and record_lifecycle:
                self._lifecycle.record_database_reverification(
                    result.plan, result.verification, receipt,
                )
            values.append(receipt)
        return tuple(values)

    def accept_postapply(self, owner_id: str, task_id: str, receipts) -> None:
        stored = {
            item.receipt_id: item
            for item in self.postapply_for_task(owner_id, task_id)
        }
        results = {
            item.plan.plan_id: item for item in self.results_for_task(
                owner_id, task_id,
            )
        }
        values = tuple(receipts)
        if not values or any(
            not item.passed or stored.get(item.receipt_id) != item
            for item in values
        ):
            raise ValueError("database post-apply evidence is not wholly successful")
        for item in values:
            result = results.get(item.plan_id)
            if result is None:
                raise ValueError("database post-apply plan is unavailable")
            self._lifecycle.record_database_reverification(
                result.plan, result.verification, item,
            )

    def postapply_for_task(self, owner_id: str, task_id: str):
        self._definition(owner_id, task_id)
        return () if self._store is None else self._store.postapply_for_task(task_id)

    def close(self) -> None:
        if self._store is not None:
            self._store.close()

    def _reconcile(
        self, definition, preparation, plan, session_id, principal_id,
    ):
        try:
            receipt = self._service.reconcile(
                plan, preparation.candidate, definition.task.grant_id,
                principal_id, session_id, lambda: False,
            )
        except Exception as error:
            raise RuntimeError(
                "database execution failed and exact compensation is unavailable"
            ) from error
        self._store.put_recovery(
            plan.plan_id, receipt, "database_execution_compensated",
        )
        return self._store.load_result(plan.plan_id)

    def _record_verified(self, result) -> None:
        if result is None or result.verification.status is not DatabaseChangeStatus.VERIFIED:
            raise RuntimeError("database engineering did not produce verified evidence")
        self._lifecycle.record_database_verification(
            result.plan, result.verification,
        )

    def _observe_owner_database(self, definition, result):
        state = self._tasks.load(definition.task.task_id)
        if state is None or state.stage not in {
            EngineeringLoopStage.APPLIED, EngineeringLoopStage.REVERIFIED,
        }:
            raise PermissionError("database post-apply lifecycle stage is invalid")
        if len(definition.task.workspace_roots) != 1:
            raise ValueError("database post-apply requires one owner workspace")
        database = secure_database_path(
            Path(definition.task.workspace_roots[0]),
            result.plan.target.database_name,
        )
        connection = sqlite3.connect(database)
        try:
            integrity = connection.execute(
                "PRAGMA integrity_check"
            ).fetchone()[0] == "ok"
            schema = sqlite_schema_digest(connection)
            data = sqlite_data_digest(connection)
        finally:
            connection.close()
        matches = (
            schema == result.verification.schema_sha256
            and data == result.verification.data_sha256
        )
        identity = hashlib.sha256(
            (
                f"{result.plan.plan_id}:{result.verification.receipt_id}:"
                f"{result.plan.approved_changeset_id}"
            ).encode()
        ).hexdigest()[:32]
        return DatabasePostapplyReceipt(
            f"database-postapply-{identity}", result.plan.task_id,
            result.plan.plan_id, result.plan.target.target_id,
            result.plan.approved_changeset_id, result.verification.receipt_id,
            schema, data, integrity, matches, integrity and matches,
            self._clock(),
            "" if integrity and matches else "owner database postcondition failed",
        )

    def _definition(self, owner_id: str, task_id: str):
        self._require_owner(owner_id)
        definition = self._tasks.load_task(task_id)
        if definition is None or definition.task.owner_id != self._owner_id:
            raise KeyError("database engineering task is unavailable")
        return definition
