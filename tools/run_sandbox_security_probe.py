#!/usr/bin/env python3
"""Capture Phase 8.2 hostile sandbox and bounded-launcher evidence."""

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from fam_os.adapters.bubblewrap import BubblewrapSandboxRunner
from fam_os.adapters.bubblewrap.process import SubprocessProcessLauncher
from fam_os.verification import IsolationLevel, SandboxLimits, SandboxRequest, SandboxStatus


PROBES = {
    "home_hidden": "from pathlib import Path; assert not Path('/home').exists()",
    "network_denied": "import socket; s=socket.socket(); assert s.connect_ex(('127.0.0.1', 9)) != 0",
    "system_write_denied": "from pathlib import Path\ntry: Path('/usr/fam-write').write_text('x')\nexcept OSError: pass\nelse: raise AssertionError('write succeeded')",
    "minimal_environment": "import os; assert set(os.environ) <= {'PATH','PYTHONHASHSEED','PWD','LC_CTYPE'}; assert os.environ.get('PWD') == '/tmp'",
}


def run_probe() -> dict[str, object]:
    runner = BubblewrapSandboxRunner()
    results = {name: asdict(runner.run(SandboxRequest(script))) for name, script in PROBES.items()}
    launcher = SubprocessProcessLauncher()
    flood = launcher.run(
        (sys.executable, "-I", "-S", "-c", "import sys\nwhile True: sys.stdout.write('x'*4096)"),
        SandboxLimits(wall_seconds=0.1, cpu_seconds=2, output_bytes=333), (),
        IsolationLevel.PROCESS_LIMITS,
    )
    timeout = launcher.run(
        (sys.executable, "-I", "-S", "-c", "while True: pass"),
        SandboxLimits(wall_seconds=0.05, cpu_seconds=2), (), IsolationLevel.PROCESS_LIMITS,
    )
    statuses = {item["status"] for item in results.values()}
    isolated = statuses == {SandboxStatus.COMPLETED.value} and all(
        item["exit_code"] == 0 for item in results.values()
    )
    unavailable = statuses == {SandboxStatus.UNAVAILABLE.value} and all(
        item["isolation"] == IsolationLevel.NONE.value for item in results.values()
    )
    return {
        "phase": "8.2",
        "bubblewrap_probes": results,
        "bubblewrap_boundary": "isolated" if isolated else "fail_closed_unavailable" if unavailable else "failed",
        "output_flood": asdict(flood),
        "timeout": asdict(timeout),
        "acceptance": (isolated or unavailable) and len(flood.stdout) == 333
        and flood.status is SandboxStatus.TIMED_OUT and timeout.status is SandboxStatus.TIMED_OUT,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = run_probe()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["acceptance"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
