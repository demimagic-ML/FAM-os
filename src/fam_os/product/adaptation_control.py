"""Durable owner control, health evaluation, and rollback for live adaptation."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import datetime, timezone
from threading import RLock

from fam_os.adaptation import (
    AdaptationControlOperation,
    AdaptationControlStatus,
    AdaptationHealthSample,
    LiveAdaptationControlRequest,
    LiveAdaptationControlState,
    VerifiedLearningOutcome,
    WorkflowAdaptationSelection,
    replace_selection,
    selection_for,
)
from fam_os.product.adaptation_health import terminal_health_sample
from fam_os.product.live_adaptation_drift import evaluate_live_drift, summarize_health


class ProductAdaptationControl:
    def __init__(self, repositories, now=None) -> None:
        self._repositories = repositories
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._lock = RLock()

    def start(self) -> None:
        with self._lock:
            self._repositories.adaptation_controls.ensure_state(
                LiveAdaptationControlState(0, True, (), (), (), self._now()),
            )
            self._reconcile_health()

    def state(self) -> LiveAdaptationControlState:
        return self._repositories.adaptation_controls.state()

    def enabled(self) -> bool:
        return self.state().enabled

    def register_snapshot(self, snapshot):
        with self._lock:
            state = self.state()
            if not state.enabled:
                return None
            self._repositories.live_adaptation.add_snapshot(snapshot)
            active = selection_for(state.active_selections, snapshot.workflow_id)
            if active is None:
                state = self._activate_initial(state, snapshot)
            elif active.snapshot_id != snapshot.snapshot_id:
                state = self._activate_candidate_if_ready(state, snapshot)
            return self._selected_snapshot(state, snapshot.workflow_id)

    def active_snapshot(self, workflow_id: str):
        state = self.state()
        if not state.enabled:
            return None
        return self._selected_snapshot(state, workflow_id)

    def terminal_committed(
        self, record, result, learning: VerifiedLearningOutcome | None,
    ) -> None:
        del learning
        with self._lock:
            observation = self._repositories.adaptation_controls.inference(record.instance_id)
            if observation is None:
                return
            sample = terminal_health_sample(observation, result, self._now())
            self._repositories.adaptation_controls.finalize_health(sample)
            self._evaluate_automatically(sample.workflow_id)

    def control(self, request: LiveAdaptationControlRequest):
        if not request.confirmed:
            raise PermissionError("adaptation control requires explicit confirmation")
        with self._lock:
            existing = self._repositories.adaptation_controls.receipt_for_request(
                request.request_id,
            )
            if existing is not None:
                return existing
            if request.operation is AdaptationControlOperation.RESET:
                return self._repositories.adaptation_controls.reset(request, self._now())
            if request.operation is AdaptationControlOperation.EVALUATE:
                return self._evaluate_requested(request)
            return self._simple_control(request)

    def health(self) -> tuple[AdaptationHealthSample, ...]:
        return self._repositories.adaptation_controls.health()

    def reports(self):
        return self._repositories.adaptation_controls.reports()

    def receipts(self):
        return self._repositories.adaptation_controls.receipts()

    def _activate_initial(self, state, snapshot):
        selection = WorkflowAdaptationSelection(snapshot.workflow_id, snapshot.snapshot_id)
        after = replace(
            state, revision=state.revision + 1,
            active_selections=replace_selection(state.active_selections, selection),
            known_good_selections=replace_selection(state.known_good_selections, selection),
            updated_at=self._now(), last_operation=AdaptationControlOperation.EVALUATE,
        )
        request = _automatic_request(
            "initial", snapshot.workflow_id, snapshot.snapshot_id, state.revision,
        )
        return self._repositories.adaptation_controls.commit(
            request, state, after, AdaptationControlStatus.APPLIED,
            ("adaptation.initial_baseline_activated",),
        ).state

    def _activate_candidate_if_ready(self, state, snapshot):
        active = selection_for(state.active_selections, snapshot.workflow_id)
        known = selection_for(state.known_good_selections, snapshot.workflow_id)
        if active is None or known is None or active.snapshot_id != known.snapshot_id:
            return state
        baseline = summarize_health(
            self._repositories.adaptation_controls.health(active.snapshot_id),
        )
        if baseline is None or snapshot.snapshot_id in state.drifted_snapshot_ids:
            return state
        selection = WorkflowAdaptationSelection(snapshot.workflow_id, snapshot.snapshot_id)
        after = replace(
            state, revision=state.revision + 1,
            active_selections=replace_selection(state.active_selections, selection),
            updated_at=self._now(), last_operation=AdaptationControlOperation.EVALUATE,
        )
        request = _automatic_request(
            "candidate", snapshot.workflow_id, snapshot.snapshot_id, state.revision,
        )
        return self._repositories.adaptation_controls.commit(
            request, state, after, AdaptationControlStatus.APPLIED,
            ("adaptation.candidate_activated", "adaptation.baseline_evidence_sufficient"),
        ).state

    def _evaluate_automatically(self, workflow_id: str) -> None:
        state = self.state()
        active, known = _selections(state, workflow_id)
        if active is None or known is None or active.snapshot_id == known.snapshot_id:
            return
        baseline = summarize_health(
            self._repositories.adaptation_controls.health(known.snapshot_id),
        )
        candidate = summarize_health(
            self._repositories.adaptation_controls.health(active.snapshot_id),
        )
        if baseline is None or candidate is None:
            return
        request = _automatic_request(
            "health", workflow_id, active.snapshot_id, state.revision,
        )
        self._evaluate(request, state, active, known)

    def _evaluate_requested(self, request):
        state = self.state()
        active, known = _selections(state, request.target_workflow_id or "")
        if active is None or known is None or active.snapshot_id == known.snapshot_id:
            return self._unchanged(
                request, state, AdaptationControlStatus.REJECTED,
                ("adaptation.candidate_unavailable",),
            )
        return self._evaluate(request, state, active, known)

    def _evaluate(self, request, state, active, known):
        baseline = summarize_health(
            self._repositories.adaptation_controls.health(known.snapshot_id),
        )
        candidate = summarize_health(
            self._repositories.adaptation_controls.health(active.snapshot_id),
        )
        if baseline is None or candidate is None:
            return self._unchanged(
                request, state, AdaptationControlStatus.REJECTED,
                ("adaptation.health_samples_insufficient",),
            )
        report = evaluate_live_drift(baseline, candidate, self._now())
        if request.request_id.startswith("adaptation-auto-health-"):
            operation = (
                AdaptationControlOperation.ROLLBACK
                if report.drifted else AdaptationControlOperation.EVALUATE
            )
            request = replace(request, operation=operation)
        after, reasons = self._evaluation_state(state, active, known, report)
        return self._repositories.adaptation_controls.commit_evaluation(
            report, request, state, after, AdaptationControlStatus.APPLIED, reasons,
        )

    def _evaluation_state(self, state, active, known, report):
        if report.drifted:
            drifted = tuple(sorted({*state.drifted_snapshot_ids, active.snapshot_id}))
            after = replace(
                state, revision=state.revision + 1,
                active_selections=replace_selection(state.active_selections, known),
                drifted_snapshot_ids=drifted, updated_at=self._now(),
                last_operation=AdaptationControlOperation.ROLLBACK,
            )
            return after, ("adaptation.drift_detected", "adaptation.known_good_restored")
        after = replace(
            state, revision=state.revision + 1,
            known_good_selections=replace_selection(state.known_good_selections, active),
            updated_at=self._now(), last_operation=AdaptationControlOperation.EVALUATE,
        )
        return after, ("adaptation.candidate_healthy", "adaptation.known_good_advanced")

    def _simple_control(self, request):
        state = self.state()
        if request.operation is AdaptationControlOperation.ENABLE:
            desired, reason = True, "adaptation.enabled"
        elif request.operation is AdaptationControlOperation.DISABLE:
            desired, reason = False, "adaptation.disabled"
        elif request.operation is AdaptationControlOperation.ROLLBACK:
            return self._rollback(request, state)
        else:
            raise ValueError("unsupported adaptation control operation")
        if state.enabled is desired:
            return self._unchanged(
                request, state, AdaptationControlStatus.NO_CHANGE,
                (f"{reason}.already",),
            )
        after = replace(
            state, revision=state.revision + 1, enabled=desired,
            updated_at=self._now(), last_operation=request.operation,
        )
        return self._repositories.adaptation_controls.commit(
            request, state, after, AdaptationControlStatus.APPLIED, (reason,),
        )

    def _rollback(self, request, state):
        workflow = request.target_workflow_id or ""
        active, known = _selections(state, workflow)
        if active is None or known is None or active.snapshot_id == known.snapshot_id:
            return self._unchanged(
                request, state, AdaptationControlStatus.NO_CHANGE,
                ("adaptation.known_good_already_active",),
            )
        after = replace(
            state, revision=state.revision + 1,
            active_selections=replace_selection(state.active_selections, known),
            drifted_snapshot_ids=tuple(sorted({*state.drifted_snapshot_ids, active.snapshot_id})),
            updated_at=self._now(), last_operation=AdaptationControlOperation.ROLLBACK,
        )
        return self._repositories.adaptation_controls.commit(
            request, state, after, AdaptationControlStatus.APPLIED,
            ("adaptation.manual_rollback", "adaptation.known_good_restored"),
        )

    def _unchanged(self, request, state, status, reasons):
        return self._repositories.adaptation_controls.commit(
            request, state, state, status, reasons,
        )

    def _selected_snapshot(self, state, workflow_id):
        selection = selection_for(state.active_selections, workflow_id)
        if selection is None or selection.snapshot_id in state.drifted_snapshot_ids:
            return None
        return self._repositories.live_adaptation.get(selection.snapshot_id)

    def _reconcile_health(self) -> None:
        for observation in self._repositories.adaptation_controls.pending_inferences():
            result = self._repositories.terminal_outcomes.result(observation.request_id)
            if result is not None:
                self._repositories.adaptation_controls.finalize_health(
                    terminal_health_sample(observation, result, self._now()),
                )
                self._evaluate_automatically(observation.workflow_id)


def _selections(state, workflow_id):
    return (
        selection_for(state.active_selections, workflow_id),
        selection_for(state.known_good_selections, workflow_id),
    )


def _automatic_request(
    stage: str, workflow_id: str, snapshot_id: str, state_revision: int,
):
    digest = hashlib.sha256(
        f"{stage}\0{workflow_id}\0{snapshot_id}\0{state_revision}".encode("utf-8"),
    ).hexdigest()
    return LiveAdaptationControlRequest(
        f"adaptation-auto-{stage}-{digest}",
        AdaptationControlOperation.EVALUATE, True, workflow_id,
    )

