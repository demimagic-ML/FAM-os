"""Inspect content-free Core route state using only installed package code."""

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
    parser.add_argument("--remote-task-id", required=True)
    parser.add_argument("--local-task-id", required=True)
    parser.add_argument("--partial-task-id")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    _installed_imports(args.installed_python, args.repository)
    from fam_os.product.composition.storage_unit import ProductStorageUnit
    from fam_os.schemas import dumps_document

    storage = ProductStorageUnit(args.state_root, os.geteuid())
    try:
        opened = storage.start()
        if opened.recovery_required or storage.core is None:
            raise RuntimeError("installed route inspection storage is unavailable")
        repositories = storage.core.repositories()
        document = {
            "remote": _record(repositories, args.remote_task_id, dumps_document),
            "local": _record(repositories, args.local_task_id, dumps_document),
        }
        if args.partial_task_id is not None:
            document["partial"] = _record(
                repositories, args.partial_task_id, dumps_document,
            )
    finally:
        storage.stop()
    args.output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    return 0


def _record(repositories, instance_id: str, dumps_document) -> dict:
    record = repositories.inference_executions.get(instance_id)
    if record is None:
        raise RuntimeError(f"installed Core record {instance_id} is unavailable")
    plan = record.remote_plan
    evidence = repositories.final_evidence.remote_execution_for_request(
        record.request_id,
    )
    recovery = repositories.final_evidence.remote_recovery_for_request(
        record.request_id,
    )
    return {
        "instance_id": record.instance_id,
        "state": record.state.value,
        "assurance": record.assurance.value,
        "failure_code": record.failure_code,
        "candidate_present": record.candidate_id is not None,
        "selection_model_ref": record.selection.model_ref,
        "selection_tier": record.selection.tier,
        "remote_plan_present": plan is not None,
        "remote_attempt_consumed": record.remote_attempt_consumed,
        "remote_plan_model_ref": None if plan is None else plan.model_ref,
        "remote_plan_expert_tier": None if plan is None else plan.expert_tier,
        "remote_execution_evidence": (
            None if evidence is None else json.loads(dumps_document(evidence))["payload"]
        ),
        "remote_recovery_evidence": (
            None if recovery is None else json.loads(dumps_document(recovery))["payload"]
        ),
    }


def _installed_imports(installed_python: Path, repository: Path) -> None:
    root = repository.resolve()
    sys.path[:] = [str(installed_python.resolve())] + [
        item for item in sys.path
        if item and not Path(item).resolve().is_relative_to(root)
    ]


if __name__ == "__main__":
    raise SystemExit(main())
