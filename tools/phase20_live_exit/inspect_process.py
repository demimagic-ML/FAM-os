"""Inspect owner-encrypted live predictions and prewarm evidence after shutdown."""

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
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--request-count", type=int, default=6)
    args = parser.parse_args()
    _installed_imports(args.installed_python, args.repository)
    from fam_os.product.composition.core_storage import CoreStorageComposition
    from fam_os.product.storage import (
        OwnerKeyStore,
        ProductionDatabase,
        SecureStorage,
        StorageSettings,
    )
    from fam_os.schemas import dumps_document

    database = ProductionDatabase(
        StorageSettings(
            args.state_root / "state/fam.sqlite3",
            os.geteuid(),
        )
    )
    storage = SecureStorage(
        database,
        OwnerKeyStore(args.state_root / "state/master.key", os.geteuid()),
    ).open()
    if storage.cipher is None:
        raise RuntimeError("installed adaptation state has no owner cipher")
    repositories = CoreStorageComposition(
        database,
        storage.cipher,
        str(os.geteuid()),
    ).repositories()
    learning = repositories.terminal_outcomes.learning_records()
    snapshots = repositories.live_adaptation.snapshots()
    receipts = repositories.live_adaptation.receipts()
    health = repositories.adaptation_controls.health()
    drift = repositories.adaptation_controls.reports()
    control_receipts = repositories.adaptation_controls.receipts()
    request_ids = tuple(f"live-{index}" for index in range(1, args.request_count + 1))
    document = {
        "learning_records": tuple(
            json.loads(dumps_document(item)) for item in learning
        ),
        "adaptation_snapshots": tuple(
            json.loads(dumps_document(item)) for item in snapshots
        ),
        "prewarm_receipts": tuple(
            json.loads(dumps_document(item)) for item in receipts
        ),
        "adaptation_control_state": json.loads(
            dumps_document(
                repositories.adaptation_controls.state(),
            )
        ),
        "adaptation_health": tuple(json.loads(dumps_document(item)) for item in health),
        "adaptation_drift_reports": tuple(
            json.loads(dumps_document(item)) for item in drift
        ),
        "adaptation_control_receipts": tuple(
            json.loads(dumps_document(item)) for item in control_receipts
        ),
        "request_prompts": {
            request_id: repositories.requests.get(request_id).prompt
            for request_id in request_ids
        },
        "terminal_results": {
            request_id: _result(repositories.terminal_outcomes.result(request_id))
            for request_id in request_ids
        },
        "learning_record_count": len(learning),
        "adaptation_snapshot_count": len(snapshots),
        "prewarm_receipt_count": len(receipts),
        "adaptation_health_count": len(health),
        "adaptation_drift_report_count": len(drift),
        "adaptation_control_receipt_count": len(control_receipts),
    }
    database.close()
    args.output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    return 0


def _result(result) -> dict | None:
    if result is None:
        return None
    return {
        "status": result.status.value,
        "assurance": result.assurance.value,
        "verified": result.verified,
        "content": result.content,
    }


def _installed_imports(installed_python: Path, repository: Path) -> None:
    root = repository.resolve()
    sys.path[:] = [str(installed_python.resolve())] + [
        item
        for item in sys.path
        if item and not Path(item).resolve().is_relative_to(root)
    ]


if __name__ == "__main__":
    raise SystemExit(main())
