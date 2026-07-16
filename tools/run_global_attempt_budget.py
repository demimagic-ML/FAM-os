#!/usr/bin/env python3
"""Capture shared repair/escalation budget enforcement evidence."""

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from fam_os.core.lifecycle import AttemptBudgetReservation, AttemptKind, GlobalAttemptBudget, InMemoryGlobalAttemptBudgetLedger


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    ledger = InMemoryGlobalAttemptBudgetLedger(GlobalAttemptBudget("plan-1", 4000, 30000, 2, 1))
    repair = ledger.reserve(AttemptBudgetReservation("r1", "plan-1", "a1", AttemptKind.REPAIR, 1500, 8000))
    escalation = ledger.reserve(AttemptBudgetReservation("r2", "plan-1", "a2", AttemptKind.ESCALATION, 2000, 12000))
    over = ledger.reserve(AttemptBudgetReservation("r3", "plan-1", "a3", AttemptKind.REPAIR, 1000, 5000))
    replay = ledger.reserve(AttemptBudgetReservation("r4", "plan-1", "a1", AttemptKind.REPAIR, 1, 1))
    document = {"phase": "8.8", "after_repair": asdict(repair), "after_escalation": asdict(escalation), "over_budget_rejected": over is None, "attempt_replay_rejected": replay is None, "acceptance": repair is not None and escalation is not None and over is None and replay is None}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    print(json.dumps(document, indent=2, sort_keys=True))
    return 0 if document["acceptance"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
