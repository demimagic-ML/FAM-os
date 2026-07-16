#!/usr/bin/env python3
import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from fam_os.adaptation import LocalOutcomePredictor, VerifiedOutcomeObservation


def main():
    root = Path(__file__).parents[1]
    paths = (
        root / "artifacts/expert_fabric/phase9.3/laguna/escalation-trace.json",
        root / "artifacts/expert_fabric/phase9.3/gemma/escalation-trace.json",
    )
    now = datetime.now(UTC)
    values = tuple(
        VerifiedOutcomeObservation(
            f"stable-toposort-{index}", "stable-toposort", now, True, 8192, True,
            hashlib.sha256(path.read_bytes()).hexdigest(),
        ) for index, path in enumerate(paths, 1)
    )
    prediction = LocalOutcomePredictor().predict(
        "phase11.2-stable-toposort", "stable-toposort", values,
    )
    output = root / "artifacts/adaptation/phase11.2/outcome-prediction.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({
        "observations": [asdict(item) for item in values],
        "prediction": asdict(prediction),
    }, indent=2, sort_keys=True, default=str) + "\n")


if __name__ == "__main__":
    main()
