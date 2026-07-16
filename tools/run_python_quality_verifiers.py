#!/usr/bin/env python3
"""Capture real Mypy/Ruff and fail-closed Python verifier evidence."""

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from fam_os.adapters.bubblewrap import BubblewrapSandboxRunner
from fam_os.adapters.python_tools import mypy_analyzer, ruff_analyzer
from fam_os.verification import VerificationRequest
from fam_os.verification.python import PythonQualityVerifier, PythonVerifier, TrustedPythonTests


GOOD = "def add(left: int, right: int) -> int:\n    return left + right\n"
BAD = "def add(left: int, right: int) -> str:\n    unused = 1\n    return left + right\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    venv = root / ".verification-venv"
    unit = PythonVerifier(
        BubblewrapSandboxRunner(), TrustedPythonTests("add.v1", "assert add(2, 3) == 5")
    )
    verifier = PythonQualityVerifier(unit, mypy_analyzer(venv), ruff_analyzer(venv))
    good = verifier.verify(VerificationRequest("python-quality-good", GOOD))
    bad_type = mypy_analyzer(venv).analyze(BAD)
    bad_static = ruff_analyzer(venv).analyze(BAD)
    report = {
        "phase": "8.3", "mypy_version": _version(venv / "bin/mypy"),
        "ruff_version": _version(venv / "bin/ruff"), "good": asdict(good),
        "negative_type": asdict(bad_type), "negative_static": asdict(bad_static),
        "release_withheld_without_isolation": not good.passed and good.unit_tests.status.value == "error",
        "acceptance": good.syntax.status.value == "passed" and good.typing.status.value == "passed"
        and good.static_analysis.status.value == "passed" and bad_type.status.value == "failed"
        and bad_static.status.value == "failed",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["acceptance"] else 1


def _version(executable: Path) -> str:
    import subprocess
    return subprocess.check_output((str(executable), "--version"), text=True).strip()


if __name__ == "__main__":
    raise SystemExit(main())
