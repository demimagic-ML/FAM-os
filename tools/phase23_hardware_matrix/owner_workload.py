"""Explicitly quiesce owner Ollama model caches for full-host qualification."""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from threading import Event, Lock, Thread
from typing import Protocol

from fam_os.adapters.ollama import OllamaRuntime, OllamaSettings
from fam_os.core.ports.inference import LoadedModel


class ModelCacheRuntime(Protocol):
    def loaded_models(self) -> tuple[LoadedModel, ...]: ...
    def unload(self, model_ref: str) -> None: ...


@dataclass(frozen=True, slots=True)
class ResidentModel:
    model_ref: str
    resident_bytes: int
    accelerator_bytes: int
    context_tokens: int


class OwnerModelQuiescence:
    """Evict cache-only residency without stopping the owner's FAM service."""

    def __init__(
        self, base_url: str, *, enabled: bool,
        runtime: ModelCacheRuntime | None = None,
        monitor_interval: float = 0.5,
    ) -> None:
        if monitor_interval <= 0:
            raise ValueError("owner model monitor interval must be positive")
        self.base_url = base_url
        self.enabled = enabled
        self._runtime = runtime or OllamaRuntime(OllamaSettings(base_url, 30))
        self._monitor_interval = monitor_interval
        self._monitor_stop = Event()
        self._monitor_thread: Thread | None = None
        self._monitor_lock = Lock()
        self._monitor_evictions: list[str] = []
        self._monitor_errors: list[str] = []
        self.before: tuple[ResidentModel, ...] = ()
        self.unloaded: tuple[str, ...] = ()

    def prepare(self) -> dict[str, object]:
        self.before = self._loaded()
        accelerator_models = tuple(
            item for item in self.before if item.accelerator_bytes > 0
        )
        if accelerator_models and not self.enabled:
            names = ", ".join(item.model_ref for item in accelerator_models)
            raise RuntimeError(
                "full-workstation qualification requires an idle owner GPU; "
                f"resident owner models: {names}; rerun with "
                "--quiesce-owner-models"
            )
        unloaded: list[str] = []
        if self.enabled:
            for item in self.before:
                self._runtime.unload(item.model_ref)
                unloaded.append(item.model_ref)
        self.unloaded = tuple(unloaded)
        after = self._wait_empty() if unloaded else self._loaded()
        return self._document(after, passed=not after)

    def start_monitor(self) -> dict[str, object]:
        """Continuously evict owner GPU caches during the explicit test window."""

        if not self.enabled:
            raise RuntimeError("owner model monitor requires explicit quiescence")
        if self._monitor_thread is not None:
            raise RuntimeError("owner model monitor is already started")
        self._monitor_stop.clear()
        self._monitor_thread = Thread(
            target=self._monitor,
            name="fam-owner-model-quiescence",
            daemon=True,
        )
        self._monitor_thread.start()
        return self.assert_idle()

    def stop_monitor(self) -> None:
        thread = self._monitor_thread
        if thread is None:
            return
        self._monitor_stop.set()
        thread.join(timeout=max(5.0, self._monitor_interval * 4))
        if thread.is_alive():
            raise RuntimeError("owner model monitor did not stop")
        self._monitor_thread = None

    def assert_idle(self) -> dict[str, object]:
        loaded = self._loaded()
        accelerator_models = tuple(
            item for item in loaded if item.accelerator_bytes > 0
        )
        if accelerator_models:
            names = ", ".join(item.model_ref for item in accelerator_models)
            raise RuntimeError(
                "owner GPU workload returned during full-workstation "
                f"qualification: {names}"
            )
        errors = self._monitor_error_snapshot()
        if errors:
            raise RuntimeError("owner model monitor failed: " + errors[-1])
        return self._document(loaded, passed=True)

    def final(self) -> dict[str, object]:
        self.stop_monitor()
        loaded = self._loaded()
        return self._document(
            loaded,
            passed=(
                not any(item.accelerator_bytes > 0 for item in loaded)
                and not self._monitor_error_snapshot()
            ),
        )

    def _monitor(self) -> None:
        while not self._monitor_stop.wait(self._monitor_interval):
            try:
                models = tuple(
                    item for item in self._loaded()
                    if item.accelerator_bytes > 0
                )
                for item in models:
                    self._runtime.unload(item.model_ref)
                    with self._monitor_lock:
                        self._monitor_evictions.append(item.model_ref)
            except Exception as error:
                with self._monitor_lock:
                    self._monitor_errors.append(
                        f"{type(error).__name__}: {error}"
                    )
                self._monitor_stop.set()

    def _monitor_error_snapshot(self) -> tuple[str, ...]:
        with self._monitor_lock:
            return tuple(self._monitor_errors)

    def _monitor_evict_snapshot(self) -> tuple[str, ...]:
        with self._monitor_lock:
            return tuple(self._monitor_evictions)

    def _wait_empty(self, timeout: float = 30) -> tuple[ResidentModel, ...]:
        deadline = time.monotonic() + timeout
        loaded = self._loaded()
        while loaded and time.monotonic() < deadline:
            time.sleep(0.1)
            loaded = self._loaded()
        if loaded:
            names = ", ".join(item.model_ref for item in loaded)
            raise RuntimeError(f"owner model cache did not quiesce: {names}")
        return loaded

    def _loaded(self) -> tuple[ResidentModel, ...]:
        return tuple(
            ResidentModel(
                item.model_ref,
                int(item.resident_bytes or 0),
                int(item.accelerator_bytes or 0),
                int(item.context_tokens or 0),
            )
            for item in self._runtime.loaded_models()
        )

    def _document(
        self, loaded: tuple[ResidentModel, ...], *, passed: bool,
    ) -> dict[str, object]:
        return {
            "base_url": self.base_url,
            "requested": self.enabled,
            "before": [asdict(item) for item in self.before],
            "unloaded": list(self.unloaded),
            "monitor_active": bool(
                self._monitor_thread is not None
                and self._monitor_thread.is_alive()
            ),
            "monitor_evictions": list(self._monitor_evict_snapshot()),
            "monitor_errors": list(self._monitor_error_snapshot()),
            "observed": [asdict(item) for item in loaded],
            "passed": passed,
            "restoration": "cache reloads automatically on the owner's next task",
        }
