#!/usr/bin/python3
"""Run a resumable minimum-24-hour installed engineering pressure soak."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time


SUITES = (
    "tests.integration.test_polyglot_engineering_sandbox",
    "tests.integration.test_design_system_exit",
    "tests.integration.test_git_publication_exit",
    "tests.integration.test_self_hosted_source_modification",
    "tests.unit.test_candidate_workspace",
    "tests.unit.test_master_engineering_loop",
    "tests.security.test_engineering_adversarial",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--installed-python", type=Path, required=True)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--duration-seconds", type=int, default=86_400)
    parser.add_argument("--interval-seconds", type=int, default=300)
    parser.add_argument("--development", action="store_true")
    args = parser.parse_args()
    if args.duration_seconds < 86_400 and not args.development:
        raise ValueError("operational engineering soak cannot be shorter than 86400 seconds")
    root = args.output_root.resolve()
    root.mkdir(parents=True, exist_ok=False, mode=0o700)
    raw = root / "events.jsonl"
    started_wall = datetime.now(timezone.utc)
    started = time.monotonic()
    iterations = failures = 0
    while time.monotonic() - started < args.duration_seconds:
        iteration_started = time.monotonic()
        result = subprocess.run(
            (str(args.installed_python.resolve()), "-m", "unittest", *SUITES, "-v"),
            cwd=args.repository.resolve(),
            env={
                "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                "LANG": "C.UTF-8", "PYTHONNOUSERSITE": "1",
                **{name: os.environ[name] for name in ("XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS") if name in os.environ},
            },
            capture_output=True, text=True, timeout=900,
        )
        iterations += 1
        failures += int(result.returncode != 0)
        event = {
            "iteration": iterations,
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "suite_seconds": round(time.monotonic() - iteration_started, 3),
            "exit_code": result.returncode,
            "stdout_sha256": hashlib.sha256(result.stdout.encode()).hexdigest(),
            "stderr_sha256": hashlib.sha256(result.stderr.encode()).hexdigest(),
            "tail": (result.stdout + result.stderr)[-4096:],
        }
        with raw.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        remaining = args.duration_seconds - (time.monotonic() - started)
        if remaining > 0:
            time.sleep(min(args.interval_seconds, remaining))
    duration = int(time.monotonic() - started)
    digest = hashlib.sha256(raw.read_bytes()).hexdigest()
    document = {
        "schema_id": "fam.engineering.pressure-soak-evidence/v1",
        "release_id": args.release_id,
        "started_at": started_wall.isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": duration,
        "iterations": iterations,
        "failed_iterations": failures,
        "raw_evidence_sha256": digest,
        "operationally_valid": duration >= 86_400 and failures == 0 and not args.development,
        "development": args.development,
    }
    (root / "summary.json").write_text(
        json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print(root / "summary.json")
    return 0 if document["operationally_valid"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
