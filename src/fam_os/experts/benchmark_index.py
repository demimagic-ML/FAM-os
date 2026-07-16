"""Atomic immutable index of expert benchmark observations."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock

from fam_os.experts.benchmark_metadata import ExpertBenchmarkRun
from fam_os.experts.registry_contracts import ExpertPackageCoordinate
from fam_os.experts.ports import ExpertBenchmarkSource


@dataclass(slots=True)
class ExpertBenchmarkIndex:
    _by_run: dict[str, ExpertBenchmarkRun] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock)

    def refresh(self, runs: tuple[ExpertBenchmarkRun, ...]) -> bool:
        updated = _validated(runs)
        with self._lock:
            changed = tuple(
                run_id for run_id in set(updated) & set(self._by_run)
                if updated[run_id] != self._by_run[run_id]
            )
            if changed:
                raise ValueError("benchmark run content changed under an existing run ID")
            if updated == self._by_run:
                return False
            self._by_run = updated
            return True

    def lookup(self, run_id: str) -> ExpertBenchmarkRun | None:
        if not run_id.strip():
            raise ValueError("benchmark run_id must not be empty")
        with self._lock:
            return self._by_run.get(run_id)

    def refresh_from(self, source: ExpertBenchmarkSource) -> bool:
        return self.refresh(source.load())

    def for_package(self, coordinate: ExpertPackageCoordinate) -> tuple[ExpertBenchmarkRun, ...]:
        with self._lock:
            values = tuple(
                run for run in self._by_run.values() if run.coordinate == coordinate
            )
        return tuple(sorted(values, key=_run_key))

    def for_suite(self, suite_id: str, suite_version: str | None = None) -> tuple[ExpertBenchmarkRun, ...]:
        if not suite_id.strip() or (suite_version is not None and not suite_version.strip()):
            raise ValueError("benchmark suite identity must not be empty")
        with self._lock:
            values = tuple(
                run for run in self._by_run.values()
                if run.suite_id == suite_id
                and (suite_version is None or run.suite_version == suite_version)
            )
        return tuple(sorted(values, key=_run_key))

    def snapshot(self) -> tuple[ExpertBenchmarkRun, ...]:
        with self._lock:
            return tuple(sorted(self._by_run.values(), key=_run_key))


def _validated(runs):
    result = {}
    for run in runs:
        if not isinstance(run, ExpertBenchmarkRun):
            raise ValueError("benchmark index requires ExpertBenchmarkRun values")
        if run.run_id in result:
            raise ValueError("duplicate benchmark run ID")
        result[run.run_id] = run
    return result


def _run_key(run):
    return run.captured_at, run.run_id
