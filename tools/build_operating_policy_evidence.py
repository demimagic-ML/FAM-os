#!/usr/bin/env python3
import json
from dataclasses import asdict
from pathlib import Path

from fam_os.adaptation.resource_policy import OperatingState, OperatingStatePolicy


def main():
    cases = {
        "battery": OperatingState(10, False, 50, .1, 0),
        "thermal": OperatingState(100, True, 90, .1, 0),
        "foreground": OperatingState(None, None, 50, .9, 0),
        "idle": OperatingState(None, None, 50, .1, 600),
    }
    policy = OperatingStatePolicy()
    output = Path(__file__).parents[1] / "artifacts/adaptation/phase11.4/operating-policy.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({key: {
        "state": asdict(state), "decision": asdict(policy.decide(state)),
    } for key, state in cases.items()}, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
