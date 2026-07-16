"""Process-scoped latency, context, CPU, RSS, and I/O measurement."""

import json
import resource
import time
from pathlib import Path

from fam_os.application_acceptance.contracts import OperationMeasurement


class OperationMeter:
    def __init__(self):
        self.measurements = []

    def measure(
        self, operation_id, level, capability_id, operation,
        context_selector=None,
    ):
        before = _sample()
        started = time.perf_counter()
        try:
            value = operation()
        except Exception:
            self._record(
                operation_id, level, capability_id, False, started, before, {},
                "acceptance.operation_failed",
            )
            raise
        context = context_selector(value) if context_selector is not None else value
        self._record(
            operation_id, level, capability_id, True, started, before, context,
        )
        return value

    def _record(
        self, operation_id, level, capability_id, succeeded, started, before,
        context, error_code=None,
    ):
        after = _sample()
        self.measurements.append(OperationMeasurement(
            operation_id, level, capability_id, succeeded,
            (time.perf_counter() - started) * 1000, _encoded_size(context),
            max(0.0, after["cpu"] - before["cpu"]),
            max(0, after["read"] - before["read"]),
            max(0, after["write"] - before["write"]),
            before["rss"], after["rss"], error_code,
        ))


def _sample():
    usage = resource.getrusage(resource.RUSAGE_SELF)
    io = _io()
    return {
        "cpu": (usage.ru_utime + usage.ru_stime) * 1000,
        "rss": _rss(), "read": io.get("read_bytes", 0),
        "write": io.get("write_bytes", 0),
    }


def _rss():
    try:
        pages = int(Path("/proc/self/statm").read_text().split()[1])
        return pages * resource.getpagesize()
    except (OSError, ValueError, IndexError):
        return 0


def _io():
    try:
        lines = Path("/proc/self/io").read_text().splitlines()
        return {key: int(value) for key, value in (line.split(": ") for line in lines)}
    except (OSError, ValueError):
        return {}


def _mutable(value):
    if hasattr(value, "items"):
        return {key: _mutable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_mutable(item) for item in value]
    if hasattr(value, "__dict__"):
        return value.__dict__
    return value


def _encoded_size(value):
    return len(json.dumps(
        _mutable(value), sort_keys=True, separators=(",", ":"), default=str,
    ).encode())
