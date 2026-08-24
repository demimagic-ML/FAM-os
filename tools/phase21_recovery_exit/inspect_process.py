"""Inspect installed content-free recovery and budget state."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--installed-python", type=Path, required=True)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    _installed_imports(args.installed_python, args.repository)

    from fam_os.core.production.attempt_budget import production_attempt_budget
    from fam_os.product.composition.storage_unit import ProductStorageUnit
    from fam_os.schemas import dumps_document

    storage = ProductStorageUnit(args.state_root, os.geteuid())
    try:
        opened = storage.start()
        if opened.recovery_required or storage.core is None:
            raise RuntimeError("installed recovery inspection storage is unavailable")
        repositories = storage.core.repositories()
        record = repositories.inference_executions.get(args.task_id)
        if record is None:
            raise RuntimeError("installed recovery inference record is unavailable")
        recovery = repositories.final_evidence.remote_recovery_for_request(
            record.request_id,
        )
        remote = repositories.final_evidence.remote_execution_for_request(
            record.request_id,
        )
        ledger = storage.core.budget_ledger(production_attempt_budget(args.task_id))
        remote_reservation = ledger.reservation(f"budget-{record.request_id}-remote")
        local_reservation = ledger.reservation(
            f"budget-{record.request_id}-local-recovery",
        )
        document = {
            "instance_id": record.instance_id,
            "request_id": record.request_id,
            "state": record.state.value,
            "assurance": record.assurance.value,
            "candidate_present": record.candidate_id is not None,
            "remote_plan_present": record.remote_plan is not None,
            "remote_attempt_consumed": record.remote_attempt_consumed,
            "selection_model_ref": record.selection.model_ref,
            "selection_tier": record.selection.tier,
            "remote_execution_evidence": _payload(remote, dumps_document),
            "remote_recovery_evidence": _payload(recovery, dumps_document),
            "remote_reservation": _payload(remote_reservation, dumps_document),
            "local_recovery_reservation": _payload(
                local_reservation, dumps_document,
            ),
            "budget": _payload(ledger.snapshot(), dumps_document),
        }
    finally:
        storage.stop()
    args.output.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )
    return 0


def _payload(value, dumps_document):
    return None if value is None else json.loads(dumps_document(value))["payload"]


def _installed_imports(installed_python: Path, repository: Path) -> None:
    root = repository.resolve()
    sys.path[:] = [str(installed_python.resolve())] + [
        item for item in sys.path
        if item and not Path(item).resolve().is_relative_to(root)
    ]


if __name__ == "__main__":
    raise SystemExit(main())
