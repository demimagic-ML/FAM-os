#!/usr/bin/env python3
"""Publish digest-bound minimum and full-workstation benchmark summaries."""

import argparse
import json
from pathlib import Path

from fam_os.product.benchmark_publication import build_publication


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cpu", type=Path, required=True)
    parser.add_argument("--workstation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    publication = build_publication(args.cpu, args.workstation)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(publication.to_dict(), indent=2, sort_keys=True) + "\n")
    print(f"published {args.output}; passed={publication.passed}")
    raise SystemExit(not publication.passed)


if __name__ == "__main__":
    main()
