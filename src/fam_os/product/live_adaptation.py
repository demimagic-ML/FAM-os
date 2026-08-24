"""Production wiring for verified frequency, context, escalation, and prewarm advice."""

from __future__ import annotations

import time
from threading import Condition, Thread

from fam_os.adaptation import (
    AdaptationControlOperation,
    LiveAdaptationSnapshot,
    LiveAdaptationControlRequest,
    ModelPrewarmReceipt,
    VerifiedLearningOutcome,
)
from fam_os.core.ports.inference import InferenceMessage
from fam_os.core.production.contracts import ModelIntent
from fam_os.product.live_prediction_builder import build_live_snapshot
from fam_os.product.adaptation_control import ProductAdaptationControl
from fam_os.product.live_adaptation_telemetry import LiveAdaptationTelemetry
from fam_os.product.live_model_prewarm import LiveModelPrewarmer


class ProductLiveAdaptation:
    def __init__(
        self, repositories, catalog, runtime, model_loader, capacity,
        health_sampler=None, now=None,
    ) -> None:
        self._repositories = repositories
        self._catalog = catalog
        self._control = ProductAdaptationControl(repositories, now)
        self._telemetry = LiveAdaptationTelemetry(
            repositories, health_sampler=health_sampler, now=now,
        )
        self._prewarmer = LiveModelPrewarmer(
            repositories, catalog, runtime, model_loader, capacity,
        )
        self._condition = Condition()
        self._pending: dict[str, str] = {}
        self._active = False
        self._stopping = False
        self._thread: Thread | None = None

    def start(self) -> None:
        self._control.start()
        with self._condition:
            if self._thread is not None:
                return
            self._stopping = False
            self._thread = Thread(
                target=self._run, name="fam-live-adaptation", daemon=True,
            )
            self._thread.start()
        workflows = {item.workflow_id for item in self._learning_records()}
        for workflow_id in sorted(workflows):
            self._register_and_queue(workflow_id)

    def stop(self) -> None:
        with self._condition:
            self._stopping = True
            self._pending.clear()
            self._condition.notify_all()
            thread = self._thread
        if thread is not None:
            thread.join(timeout=30)
        with self._condition:
            self._thread = None

    def learning_committed(self, learning: VerifiedLearningOutcome) -> None:
        if not learning.verified or not learning.local_only:
            raise ValueError("live adaptation requires verified local learning")
        if self._control.enabled():
            self._register_and_queue(learning.workflow_id)

    def terminal_committed(self, record, snapshot, result, learning) -> None:
        del snapshot
        if learning is not None:
            self.learning_committed(learning)
        self._control.terminal_committed(record, result, learning)

    def preferred_model_refs(self, intent: ModelIntent) -> tuple[str, ...]:
        snapshot = self.refresh(f"intent:{intent.value}")
        return () if snapshot is None else snapshot.frequency_model_refs

    def context_tokens(
        self,
        request_id: str,
        intent: ModelIntent,
        model_ref: str,
        messages: tuple[InferenceMessage, ...],
        max_output_tokens: int,
        default_context_tokens: int,
    ) -> int:
        if not request_id.strip():
            raise ValueError("adapted context request identity must not be empty")
        model = self._catalog.get(model_ref)
        limit = min(
            default_context_tokens,
            default_context_tokens if model is None else model.max_context_tokens,
        )
        snapshot = self.refresh(f"intent:{intent.value}")
        if any(message.images for message in messages):
            selected = limit
        else:
            minimum = _minimum_context_tokens(messages, max_output_tokens)
            selected = (
                min(limit, minimum)
                if snapshot is None
                else min(limit, max(minimum, snapshot.predicted_context_tokens))
            )
        self._telemetry.remember(request_id, snapshot, selected, limit)
        return selected

    def inference_completed(
        self, observation_id: str, request_id: str,
        intent: ModelIntent, model_ref: str, metrics,
    ) -> None:
        del intent
        self._telemetry.inference_completed(
            observation_id, request_id, model_ref, metrics,
        )

    def refresh(self, workflow_id: str) -> LiveAdaptationSnapshot | None:
        if not self._control.enabled():
            return None
        snapshot = self._latest_snapshot(workflow_id)
        return None if snapshot is None else self._control.register_snapshot(snapshot)

    def snapshots(self) -> tuple[LiveAdaptationSnapshot, ...]:
        return self._repositories.live_adaptation.snapshots()

    def receipts(self) -> tuple[ModelPrewarmReceipt, ...]:
        return self._repositories.live_adaptation.receipts()

    def control_state(self):
        return self._control.state()

    def health(self):
        return self._control.health()

    def drift_reports(self):
        return self._control.reports()

    def control_receipts(self):
        return self._control.receipts()

    def apply_control(self, request: LiveAdaptationControlRequest):
        receipt = self._control.control(request)
        if request.operation in {
            AdaptationControlOperation.DISABLE, AdaptationControlOperation.RESET,
        }:
            self._telemetry.clear()
            with self._condition:
                self._pending.clear()
        if request.operation is AdaptationControlOperation.ENABLE and receipt.state.enabled:
            for workflow_id in sorted({item.workflow_id for item in self._learning_records()}):
                self._register_and_queue(workflow_id)
        return receipt

    def wait_for_idle(self, timeout: float = 30) -> bool:
        deadline = time.monotonic() + timeout
        with self._condition:
            while self._pending or self._active:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._condition.wait(remaining)
        return True

    def _learning_records(self):
        return self._repositories.terminal_outcomes.learning_records()

    def _queue(self, workflow_id: str, snapshot_id: str) -> None:
        with self._condition:
            if self._thread is None or self._stopping:
                return
            self._pending[workflow_id] = snapshot_id
            self._condition.notify_all()

    def _run(self) -> None:
        while True:
            with self._condition:
                while not self._pending and not self._stopping:
                    self._condition.wait()
                if self._stopping:
                    return
                workflow_id = min(self._pending)
                snapshot_id = self._pending.pop(workflow_id)
                self._active = True
            try:
                self._prewarm(snapshot_id)
            finally:
                with self._condition:
                    self._active = False
                    self._condition.notify_all()

    def _prewarm(self, snapshot_id: str) -> None:
        state = self._control.state()
        if not state.enabled or snapshot_id in state.drifted_snapshot_ids:
            return
        snapshot = self._repositories.live_adaptation.get(snapshot_id)
        if snapshot is None:
            return
        self._prewarmer.execute(snapshot)

    def _register_and_queue(self, workflow_id: str) -> None:
        snapshot = self._latest_snapshot(workflow_id)
        if snapshot is None:
            return
        self._control.register_snapshot(snapshot)
        self._queue(workflow_id, snapshot.snapshot_id)

    def _latest_snapshot(self, workflow_id: str):
        records = self._learning_records()
        values = tuple(item for item in records if item.workflow_id == workflow_id)
        if len(values) < 2:
            return None
        return build_live_snapshot(
            workflow_id, records, self._catalog, values[-1].observed_at,
        )


def _minimum_context_tokens(messages, max_output_tokens: int) -> int:
    prompt_bytes = sum(len(message.content.encode("utf-8")) for message in messages)
    estimated = max(128, prompt_bytes + max_output_tokens + 512)
    return min(32_768, 1 << (estimated - 1).bit_length())
