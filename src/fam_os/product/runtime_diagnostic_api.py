"""Owner-scoped product composition for policy-selected runtime diagnostics."""

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from fam_os.adapters.filesystem import CandidateWorkspaceAdapter
from fam_os.core.engineering import (
    EngineeringLoopStage, EngineeringSandboxProfile,
    RuntimeDiagnosticIntentPolicy, RuntimeDiagnosticPhase,
    RuntimeDiagnosticStatus, RuntimePerformanceBaseline,
)


class ProductRuntimeDiagnosticApi:
    def __init__(
        self, owner_id, tasks, preparations, candidate_root: Path, catalog,
        service, store, require_owner, validate_grant, *, clock=None,
    ) -> None:
        self._owner_id = owner_id
        self._tasks = tasks
        self._preparations = preparations
        self._candidate_root = candidate_root
        self._policy = RuntimeDiagnosticIntentPolicy(catalog)
        self._service = service
        self._store = store
        self._require_owner = require_owner
        self._validate_grant = validate_grant
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def requested(self, owner_id: str, task_id: str) -> bool:
        definition = self._definition(owner_id, task_id)
        return bool(self._policy.requested_kinds(definition.task.intent))

    def execute_selected(
        self, owner_id: str, task_id: str, *, session_id: str,
        principal_id: str, preferred_paths=(), postapply: bool = False,
    ):
        definition = self._definition(owner_id, task_id)
        preparation = self._preparations.load(task_id)
        state = self._tasks.load(task_id)
        if preparation is None or state is None:
            raise KeyError("runtime diagnostic preparation is unavailable")
        expected = (
            {EngineeringLoopStage.APPLIED, EngineeringLoopStage.REVERIFIED}
            if postapply else
            {EngineeringLoopStage.CANDIDATE_READY, EngineeringLoopStage.VERIFIED}
        )
        if state.stage not in expected:
            raise PermissionError("runtime diagnostic lifecycle stage is invalid")
        self._validate_grant(
            task_id, definition.task.grant_id, self._clock(),
        )
        adapter = CandidateWorkspaceAdapter(
            Path(preparation.candidate.owner_workspace), self._candidate_root,
        )
        if postapply:
            preparation = replace(
                preparation, candidate=adapter.create(task_id),
            )
        entries = adapter.current_entries(preparation.candidate)
        requests = self._policy.plan(
            definition, preparation.candidate, entries,
            tuple(preferred_paths),
            phase=(
                RuntimeDiagnosticPhase.POSTAPPLY
                if postapply else RuntimeDiagnosticPhase.CANDIDATE
            ),
            session_id=session_id, principal_id=principal_id,
            now=self._clock(),
            baselines=self._baselines(task_id),
        )
        if requests and (self._service is None or self._store is None):
            raise RuntimeError("installed runtime diagnostics were not composed")
        receipts = tuple(
            self._service.execute(
                definition, preparation, request, _profile(request),
            )
            for request in requests
        )
        return requests, receipts

    def capture_performance_baseline(
        self, owner_id: str, task_id: str, *, session_id: str,
        principal_id: str, preferred_paths=(),
    ):
        definition = self._definition(owner_id, task_id)
        preparation = self._preparations.load(task_id)
        state = self._tasks.load(task_id)
        if preparation is None or state is None:
            raise KeyError("performance baseline preparation is unavailable")
        if state.stage is not EngineeringLoopStage.CANDIDATE_READY:
            existing = tuple(
                item for item in self.requests_for_task(owner_id, task_id)
                if item.phase is RuntimeDiagnosticPhase.BASELINE
            )
            if existing:
                ids = {item.request_id for item in existing}
                receipts = tuple(
                    item for item in self.receipts_for_task(owner_id, task_id)
                    if item.request_id in ids
                )
                if {item.request_id for item in receipts} == ids:
                    return existing, receipts
            raise PermissionError("performance baseline requires pristine candidate state")
        self._validate_grant(
            task_id, definition.task.grant_id, self._clock(),
        )
        adapter = CandidateWorkspaceAdapter(
            Path(preparation.candidate.owner_workspace), self._candidate_root,
        )
        entries = adapter.current_entries(preparation.candidate)
        requests = self._policy.plan_performance_baseline(
            definition, preparation.candidate, entries,
            tuple(preferred_paths), session_id=session_id,
            principal_id=principal_id, now=self._clock(),
        )
        if requests and (self._service is None or self._store is None):
            raise RuntimeError("installed performance diagnostics were not composed")
        receipts = tuple(
            self._service.execute(
                definition, preparation, request, _profile(request),
            ) for request in requests
        )
        return requests, receipts

    def requests_for_task(self, owner_id: str, task_id: str):
        self._definition(owner_id, task_id)
        return () if self._store is None else self._store.requests_for_task(task_id)

    def receipts_for_task(self, owner_id: str, task_id: str):
        self._definition(owner_id, task_id)
        return () if self._store is None else self._store.receipts_for_task(task_id)

    def close(self) -> None:
        if self._store is not None:
            self._store.close()

    def _definition(self, owner_id: str, task_id: str):
        self._require_owner(owner_id)
        definition = self._tasks.load_task(task_id)
        if definition is None or definition.task.owner_id != self._owner_id:
            raise KeyError("runtime diagnostic engineering task is unavailable")
        return definition

    def _baselines(self, task_id: str):
        if self._store is None:
            return {}
        requests = {
            item.request_id: item for item in self._store.requests_for_task(task_id)
            if item.phase is RuntimeDiagnosticPhase.BASELINE
        }
        values = {}
        for receipt in self._store.receipts_for_task(task_id):
            request = requests.get(receipt.request_id)
            if request is None:
                continue
            if (
                receipt.status is not RuntimeDiagnosticStatus.PASSED
                or receipt.baseline_artifact_sha256 is None
                or receipt.observed_value_microunits is None
                or request.maximum_regression_ppm is None
            ):
                raise RuntimeError("captured performance baseline is incomplete")
            values[request.target_argv[0]] = RuntimePerformanceBaseline(
                receipt.baseline_artifact_sha256,
                receipt.observed_value_microunits,
                request.maximum_regression_ppm,
            )
        return values


def _profile(request):
    limits = request.limits
    return EngineeringSandboxProfile(
        f"runtime-diagnostic-profile-{request.request_id}",
        limits.memory_bytes, limits.cpu_seconds, limits.wall_seconds,
        limits.process_limit, limits.output_bytes, limits.temporary_file_bytes,
        request.network_mode, request.network_destinations, (),
    )
