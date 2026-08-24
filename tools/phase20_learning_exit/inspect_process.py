"""Inspect installed encrypted terminal and learning records after shutdown."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


REQUEST_IDS = ("learning-verified", "learning-unverified")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--installed-python", type=Path, required=True)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    _installed_imports(args.installed_python, args.repository)
    from fam_os.product.composition.core_storage import CoreStorageComposition
    from fam_os.product.storage import (
        OwnerKeyStore, ProductionDatabase, SecureStorage, StorageSettings,
    )
    from fam_os.schemas import dumps_document

    database = ProductionDatabase(StorageSettings(
        args.state_root / "state/fam.sqlite3", os.geteuid(),
    ))
    storage = SecureStorage(
        database, OwnerKeyStore(args.state_root / "state/master.key", os.geteuid()),
    ).open()
    if storage.cipher is None:
        raise RuntimeError("installed outcome state opened without its owner cipher")
    repositories = CoreStorageComposition(
        database, storage.cipher, str(os.geteuid()),
    ).repositories()
    learning = repositories.terminal_outcomes.learning_records()
    candidates = _candidates(database, repositories)
    runs = tuple(
        run for request_id in REQUEST_IDS
        for run in repositories.verifications.runs_for_request(request_id)
    )
    document = {
        "request_prompts": {
            request_id: _prompt(repositories, request_id)
            for request_id in REQUEST_IDS
        },
        "terminal_results": {
            request_id: _result(repositories.terminal_outcomes.result(request_id))
            for request_id in REQUEST_IDS
        },
        "learning_records": tuple(json.loads(dumps_document(item)) for item in learning),
        "candidate_contents": candidates,
        "verification_run_feedback": tuple(run.feedback for run in runs),
        "verification_declaration_count": database.execute(
            "SELECT count(*) FROM verification_declarations",
        ).fetchone()[0],
        "terminal_result_count": database.execute(
            "SELECT count(*) FROM terminal_results",
        ).fetchone()[0],
        "learning_record_count": len(learning),
    }
    database.close()
    args.output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    return 0


def _candidates(database, repositories) -> dict[str, str]:
    rows = database.fetchall(
        "SELECT evidence_id FROM final_evidence "
        "WHERE evidence_kind='candidate' ORDER BY evidence_id",
    )
    return {
        str(row[0]): repositories.final_evidence.candidate(str(row[0])).content
        for row in rows
    }


def _result(result) -> dict | None:
    if result is None:
        return None
    return {
        "status": result.status.value,
        "assurance": result.assurance.value,
        "verified": result.verified,
        "content": result.content,
    }


def _prompt(repositories, request_id: str) -> str:
    request = repositories.requests.get(request_id)
    if request is None:
        raise RuntimeError(f"installed terminal request is missing: {request_id}")
    return request.prompt


def _installed_imports(installed_python: Path, repository: Path) -> None:
    root = repository.resolve()
    sys.path[:] = [str(installed_python.resolve())] + [
        item for item in sys.path
        if item and not Path(item).resolve().is_relative_to(root)
    ]


if __name__ == "__main__":
    raise SystemExit(main())
