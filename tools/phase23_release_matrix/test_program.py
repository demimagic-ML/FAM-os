"""Run one unittest discovery target and emit machine-readable results."""

from __future__ import annotations

import argparse
import json
import os
import time
import unittest
from pathlib import Path

import fam_os


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-directory", required=True)
    parser.add_argument("--pattern", default="test*.py")
    parser.add_argument("--top-level", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--log", type=Path, required=True)
    args = parser.parse_args()
    suite = unittest.defaultTestLoader.discover(
        args.start_directory, pattern=args.pattern, top_level_dir=args.top_level,
    )
    started = time.monotonic()
    with args.log.open("w", encoding="utf-8") as stream:
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    module_path = Path(fam_os.__file__).resolve()
    document = {
        "duration_seconds": round(time.monotonic() - started, 6),
        "errors": tuple(test.id() for test, _traceback in result.errors),
        "expected_failures": tuple(
            test.id() for test, _traceback in result.expectedFailures
        ),
        "failures": tuple(test.id() for test, _traceback in result.failures),
        "module_path": str(module_path),
        "passed": result.wasSuccessful(),
        "skipped": tuple(
            {"reason": str(reason), "test_id": test.id()}
            for test, reason in result.skipped
        ),
        "tests_run": result.testsRun,
        "unexpected_successes": tuple(test.id() for test in result.unexpectedSuccesses),
    }
    descriptor = os.open(
        args.output, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600,
    )
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(document, stream, indent=2, sort_keys=True)
        stream.write("\n")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())

