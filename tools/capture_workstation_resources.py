"""Capture strict privacy-reviewed resources for a full-workstation run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from fam_os.scheduler import StorageMedium
from tools.workstation.capture import capture_live_workstation


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument(
        "--storage-medium",
        choices=tuple(item.value for item in StorageMedium),
        default=StorageMedium.NVME.value,
    )
    args = parser.parse_args()
    capture = capture_live_workstation(
        args.profile, args.output_root, StorageMedium(args.storage_medium)
    )
    print(
        json.dumps(
            {
                "capture_directory": str(capture.directory),
                "effective_budget": str(capture.budget_path),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
