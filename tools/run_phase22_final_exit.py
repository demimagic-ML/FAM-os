#!/usr/bin/env python3
"""Seal the aggregate signed-installed Phase 22 exit evidence and remove it."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from tools.phase22_release_exit.final_evidence import finalize_phase22_exit


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--training-evidence", type=Path, required=True)
    parser.add_argument("--release-evidence", type=Path, required=True)
    parser.add_argument("--installation-prefix", type=Path, required=True)
    parser.add_argument("--release-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    evidence = finalize_phase22_exit(
        training_evidence_path=arguments.training_evidence.absolute(),
        release_evidence_path=arguments.release_evidence.absolute(),
        installation_prefix=arguments.installation_prefix.absolute(),
        release_manifest_path=arguments.release_manifest.absolute(),
        output_path=arguments.output.absolute(),
    )
    print(json.dumps({
        "evidence": str(arguments.output.absolute()),
        "passed": evidence["passed"],
    }, sort_keys=True))
    return 0 if evidence["passed"] is True else 2


if __name__ == "__main__":
    raise SystemExit(main())
