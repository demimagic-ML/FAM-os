#!/usr/bin/env python3
"""Run the real Phase 5.12 Shell/Application Fabric acceptance."""

import argparse
from pathlib import Path

from fam_os.application_acceptance.runner import Phase5AcceptanceRunner


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", type=Path,
        default=Path("artifacts/application_fabric/phase5_acceptance.json"),
    )
    arguments = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    report = Phase5AcceptanceRunner(root, arguments.output).run()
    print(f"Phase 5.12 exit gate: {'PASS' if report.exit_gate_passed else 'FAIL'}")
    print(arguments.output.resolve())
    return 0 if report.exit_gate_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
