#!/usr/bin/env python3
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from fam_os.scheduler.frequency_learning import ExpertUseObservation, LocalExpertFrequencyLearner


def main():
    now = datetime.now(UTC)
    observations = tuple(
        ExpertUseObservation(f"use-{index}", expert, now, verified)
        for index, (expert, verified) in enumerate((
            ("expert.micro.routing-v1", True), ("expert.micro.routing-v1", True),
            ("expert.language.llama3.2-3b", True), ("expert.code.qwen2.5-coder-7b", False),
        ), 1)
    )
    profile = LocalExpertFrequencyLearner().learn("phase11.1-local-v1", observations)
    output = Path(__file__).parents[1] / "artifacts/adaptation/phase11.1/expert-frequency.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(asdict(profile), indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
