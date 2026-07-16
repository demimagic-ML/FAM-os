#!/usr/bin/env python3
import json
from dataclasses import asdict
from pathlib import Path

from fam_os.memory.phase10_exit import Phase10ExitEvidence


def main():
    root = Path(__file__).parents[1]
    management = json.loads((root / "artifacts/memory/phase10.5/memory-management-evidence.json").read_text())
    quality = json.loads((root / "artifacts/memory/phase10.7/memory-quality-privacy.json").read_text())
    evidence = Phase10ExitEvidence(
        "phase10-exit-v1", management["inspected"], management["deletion_payload_removed"],
        management["remaining_chunk_count"] == 0, quality["cross_owner_hit_count"],
        quality["plaintext_leak_count"], quality["top1_accuracy"],
        management["passed"] and quality["passed"],
    )
    (root / "artifacts/memory/phase10-exit.json").write_text(
        json.dumps(asdict(evidence), indent=2, sort_keys=True) + "\n",
    )


if __name__ == "__main__":
    main()
