"""Core admission and durable execution for candidate runtime diagnostics."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Protocol
from uuid import uuid4

from fam_os.core.engineering.authority import (
    EngineeringAuthority, EngineeringOperation,
)
from fam_os.core.engineering.diagnostic_policy import RuntimeDiagnosticRecipePolicy
from fam_os.core.engineering.diagnostic_redaction import sanitize_diagnostic_evidence
from fam_os.core.engineering.diagnostics import (
    RuntimeDiagnosticReceipt, RuntimeDiagnosticRequest, RuntimeDiagnosticStatus,
    validate_runtime_diagnostic_receipt,
)
from fam_os.core.engineering.execution import EngineeringSandboxProfile
from fam_os.core.engineering.grants import (
    EngineeringAuthorizationRequest, EngineeringResourceImpact,
)


class RuntimeDiagnosticStore(Protocol):
    def put_request(self, request: RuntimeDiagnosticRequest) -> None: ...
    def load_request(self, request_id: str): ...
    def put_receipt(self, receipt: RuntimeDiagnosticReceipt) -> None: ...
    def load_receipt(self, request_id: str): ...


class RuntimeDiagnosticRunner(Protocol):
    def run(
        self, request, candidate, profile, *, authorization_decision_ids,
    ) -> RuntimeDiagnosticReceipt: ...


class RuntimeDiagnosticService:
    """Execute only an exact signed request under two live authority checks."""

    def __init__(
        self, authorizer, recipes: RuntimeDiagnosticRecipePolicy,
        runner: RuntimeDiagnosticRunner, store: RuntimeDiagnosticStore,
        *, clock=None, identifier=None,
    ) -> None:
        self._authorizer = authorizer
        self._recipes = recipes
        self._runner = runner
        self._store = store
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._identifier = identifier or (lambda: uuid4().hex)

    def execute(self, definition, preparation, request, profile):
        self._validate(definition, preparation, request, profile)
        existing_request = self._store.load_request(request.request_id)
        if existing_request is not None and existing_request != request:
            raise RuntimeError("runtime diagnostic request identity conflicts")
        existing_receipt = self._store.load_receipt(request.request_id)
        if existing_receipt is not None:
            validate_runtime_diagnostic_receipt(request, existing_receipt)
            return existing_receipt
        self._authorize(definition, preparation, request)
        self._store.put_request(request)
        live = self._authorize(definition, preparation, request)
        try:
            receipt = self._runner.run(
                request, preparation.candidate, profile,
                authorization_decision_ids=(live.decision_id,),
            )
            validate_runtime_diagnostic_receipt(request, receipt)
        except Exception as error:
            receipt = self._unavailable(request, profile, live.decision_id, error)
        self._store.put_receipt(receipt)
        return receipt

    def _authorize(self, definition, preparation, request):
        task = definition.task
        value = EngineeringAuthorizationRequest(
            f"runtime-diagnostic-auth-{self._identifier()}", request.grant_id,
            request.principal_id, EngineeringAuthority.EXECUTE,
            request.task_id, request.session_id, request.request_id, None,
            preparation.candidate.owner_workspace, request.target_argv[0],
            None, None, None, None, None, None,
            EngineeringResourceImpact(
                request.limits.wall_seconds, 1, request.limits.process_limit,
                0, 0, 0,
            ),
        )
        decision = self._authorizer.authorize(value)
        if (
            not decision.allowed or decision.request_id != value.request_id
            or decision.grant_id != task.grant_id
            or decision.authority is not EngineeringAuthority.EXECUTE
        ):
            raise PermissionError("runtime diagnostic lacks exact live execute authority")
        return decision

    def _validate(self, definition, preparation, request, profile) -> None:
        task = definition.task
        if (
            request.task_id != task.task_id
            or request.candidate_id != preparation.candidate.candidate_id
            or request.grant_id != task.grant_id
            or request.principal_id != task.owner_id
            or preparation.definition_id != definition.definition_id
        ):
            raise ValueError("runtime diagnostic differs from durable engineering task")
        if (
            EngineeringAuthority.EXECUTE not in task.authorities
            or EngineeringOperation.RUN_TOOL not in task.permitted_operations
        ):
            raise PermissionError("runtime diagnostic is outside durable task authority")
        if not task.created_at <= request.created_at < task.expires_at:
            raise PermissionError("runtime diagnostic request is outside task lifetime")
        if request.limits.wall_seconds > task.max_wall_seconds:
            raise PermissionError("runtime diagnostic exceeds task wall budget")
        if profile.network_mode is not request.network_mode:
            raise PermissionError("runtime diagnostic profile changes network policy")
        self._recipes.admit(request)

    def _unavailable(self, request, profile, decision_id, error):
        instant = self._clock()
        empty = hashlib.sha256(b"").hexdigest()
        return RuntimeDiagnosticReceipt(
            f"diagnostic-receipt-{self._identifier()}", request.request_id,
            request.task_id, request.candidate_id, request.signed_recipe_id,
            request.signed_recipe_version, request.recipe_payload_sha256,
            profile.profile_id, instant, instant,
            RuntimeDiagnosticStatus.UNAVAILABLE, None, empty, empty, (), (),
            (), (decision_id,), request.baseline_artifact_sha256,
            diagnostic=sanitize_diagnostic_evidence(
                f"{type(error).__name__}: runtime diagnostic execution unavailable"
            ),
            performance_mode=request.performance_mode,
        )
