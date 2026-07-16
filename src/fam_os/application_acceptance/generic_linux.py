"""Read-only generic bridge probe against an unmodified Linux application."""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from fam_os.adapters.linux.accessibility import (
    AccessibilityBridgePolicy, GiAtspiProvider, LinuxAccessibilityBridge,
)


def observe_unmodified_zenity(zenity_path: Path, timeout_seconds=10.0):
    _enable_system_gi()
    provider = GiAtspiProvider()
    before = _process_ids(provider)
    process = subprocess.Popen(
        (str(zenity_path), "--info", "--text=FAM_OS acceptance observation"),
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, start_new_session=True,
    )
    try:
        bridge = LinuxAccessibilityBridge(
            provider, AccessibilityBridgePolicy(
                maximum_nodes=64, maximum_depth=4,
                maximum_text_characters=128, maximum_actions_per_node=8,
            ),
        )
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            for process_id in _process_ids(provider) - before:
                snapshot = bridge.observe(process_id, include_text=False)
                if snapshot.nodes:
                    return {
                        "process_id": process_id, "node_count": len(snapshot.nodes),
                        "truncated": snapshot.truncated,
                        "protected_count": sum(item.protected for item in snapshot.nodes),
                    }
            time.sleep(0.1)
        raise TimeoutError("unmodified Linux application was not accessible")
    finally:
        _terminate(process)


def _process_ids(provider):
    values = set()
    if not provider.available():
        return values
    for root in provider.roots():
        try:
            node = provider.read(root, 0)
        except Exception:
            continue
        if node.process_id > 0:
            values.add(node.process_id)
    return values


def _enable_system_gi():
    try:
        import gi  # noqa: F401
        return
    except ImportError:
        path = "/usr/lib/python3/dist-packages"
        if Path(path).is_dir() and path not in sys.path:
            sys.path.append(path)


def _terminate(process):
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=3)
