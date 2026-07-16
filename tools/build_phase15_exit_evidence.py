#!/usr/bin/env python3
"""Build the digest-bound installed operational exit report."""

import json
from pathlib import Path

from fam_os.product.phase15_exit import build_phase15_exit


def main() -> None:
    report = build_phase15_exit(
        Path("artifacts/product/phase15/installed-operational-acceptance.json"),
        Path("artifacts/product/phase15/operational-service-soak.json"),
    )
    output = Path("artifacts/product/phase15/phase15-exit.json")
    output.write_text(json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n")
    print(json.dumps(report.to_dict(), sort_keys=True))
    raise SystemExit(not report.passed)


if __name__ == "__main__":
    main()
