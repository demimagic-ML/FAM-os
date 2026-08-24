"""Bounded ownership and joining of per-task production workers."""

from __future__ import annotations

from collections.abc import Callable
from threading import Lock, Thread, current_thread


class TaskWorkerRegistry:
    def __init__(self) -> None:
        self._workers: dict[str, Thread] = {}
        self._lock = Lock()

    def start(self, instance_id: str, target: Callable[[str], None]) -> None:
        with self._lock:
            worker = self._workers.get(instance_id)
            if worker is not None and worker.is_alive():
                return
            worker = Thread(
                target=self._run,
                args=(instance_id, target),
                name=f"fam-task-{instance_id}",
                daemon=True,
            )
            self._workers[instance_id] = worker
            worker.start()

    def wait(self, instance_id: str, timeout: float = 30) -> None:
        with self._lock:
            worker = self._workers.get(instance_id)
        if worker is None or worker is current_thread():
            return
        worker.join(timeout)
        if worker.is_alive():
            raise TimeoutError(f"task worker did not finish: {instance_id}")

    def active_ids(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(sorted(
                key for key, worker in self._workers.items() if worker.is_alive()
            ))

    def _run(self, instance_id: str, target: Callable[[str], None]) -> None:
        try:
            target(instance_id)
        finally:
            with self._lock:
                if self._workers.get(instance_id) is current_thread():
                    self._workers.pop(instance_id, None)
