#!/usr/bin/python3
"""Run the real source polyglot sandbox matrix and preserve raw JSON evidence."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time


ECOSYSTEMS = (
    "python", "javascript", "typescript", "rust", "go", "java", "kotlin",
    "c", "cpp", "shell", "html", "css",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    environment = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "PYTHONPATH": f"{root / 'src'}:{root}",
        "LANG": "C.UTF-8",
    }
    for name in ("XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS"):
        if name in os.environ:
            environment[name] = os.environ[name]
    command = (
        sys.executable, "-m", "unittest",
        "tests.integration.test_polyglot_engineering_sandbox", "-v",
    )
    started = time.monotonic()
    result = subprocess.run(
        command, cwd=root, env=environment, capture_output=True, text=True,
        timeout=300,
    )
    elapsed = time.monotonic() - started
    passed = result.returncode == 0
    document = {
        "schema_id": "fam.engineering.polyglot-source-qualification/v1",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "scope": "source_checkout_not_installed_release",
        "command": list(command),
        "elapsed_seconds": round(elapsed, 6),
        "exit_code": result.returncode,
        "ecosystems": [
            {
                "ecosystem": ecosystem,
                "positive_fixture": "passed" if passed else "not_proven",
                "negative_fixture": "rejected_as_expected" if passed else "not_proven",
                "containment": "bubblewrap+cgroup+rlimits" if passed else "not_proven",
            }
            for ecosystem in ECOSYSTEMS
        ],
        "stdout": result.stdout[-16_384:],
        "stderr": result.stderr[-16_384:],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print(args.output)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
