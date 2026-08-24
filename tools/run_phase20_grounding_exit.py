#!/usr/bin/env python3
"""Build and qualify signed installed Phase 20.3 grounded answers."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from tools.phase19_exit.release_environment import build_and_install
from tools.phase20_grounding_exit.installed_service import InstalledGroundingService
from tools.phase20_grounding_exit.scenario import first_process_scenario, restarted_process_scenario
from tools.phase20_index_exit.model_root import create_model_root


PROJECT_NONCE = "PHASE20_GROUNDED_PROJECT_NONCE: CPU GPU RAM and SSD form one local fabric."
PRIVATE_NONCE = "MCP_ONLY_PRIVATE_NONCE must never reach a fam.shell prompt."


def main() -> int:
    repository = Path(__file__).resolve().parents[1]
    output = repository / "artifacts/memory/phase20.3-grounded-answers.json"
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        installation, manifest, _connector, _extensions = build_and_install(
            repository, root, "phase20-grounding-exit", "phase20-grounding-test",
        )
        model_root = create_model_root(root / "models")
        project_file, private_file = _documents(root / "documents")
        product_root = root / "product"
        product_root.mkdir()
        with InstalledGroundingService(
            installation, repository, product_root, model_root, root / "run-1",
        ) as service:
            first = first_process_scenario(service, project_file, private_file)
        first_observations = _read(service.observations)
        with InstalledGroundingService(
            installation, repository, product_root, model_root, root / "run-2",
        ) as restarted:
            second = restarted_process_scenario(restarted)
        restart_observations = _read(restarted.observations)
        diagnosis = installation.diagnose()
        document = {
            "phase": "20.3",
            "release_id": manifest.release_id,
            "signer_key_id": manifest.signer_key_id,
            "release_component_count": len(manifest.components),
            "signed_install_healthy": diagnosis.healthy,
            "first_process": first,
            "first_process_observations": first_observations,
            "restarted_process": second,
            "restart_observations": restart_observations,
        }
        document["passed"] = _passed(document)
        installation.remove()
        document["complete_removal"] = not installation.prefix.exists()
        document["passed"] = document["passed"] and document["complete_removal"]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    print(json.dumps(document, indent=2, sort_keys=True))
    return 0 if document["passed"] else 1


def _documents(root: Path) -> tuple[Path, Path]:
    root.mkdir()
    project = root / "README.md"
    project.write_text(PROJECT_NONCE, encoding="utf-8")
    private = root / "private.txt"
    private.write_text(PRIVATE_NONCE, encoding="utf-8")
    return project, private


def _read(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def _passed(document: dict) -> bool:
    first = document["first_process"]
    identity, project, cross = first["identity"], first["project"], first["cross_scope"]
    restarted = document["restarted_process"]
    tasks = (identity, project, cross, restarted)
    runs = [run for task in tasks for run in task["verification_runs"]]
    return bool(
        document["signed_install_healthy"]
        and document["release_component_count"] == 7
        and first["no_source"]
        and first["project_receipt"]["passed"]
        and first["private_receipt"]["passed"]
        and all(task["status"] == "verified" and task["citations"] for task in tasks)
        and identity["citations"][0]["source_locator"].startswith("package://")
        and PROJECT_NONCE in project["content"]
        and project["citations"][0]["quoted_text"] == PROJECT_NONCE
        and PRIVATE_NONCE not in cross["content"]
        and PRIVATE_NONCE not in json.dumps(cross["citations"])
        and PROJECT_NONCE in restarted["content"]
        and all(run["status"] == "passed" and run["effective_trust"] == "signed" for run in runs)
        and not any(item["contains_forbidden_secret"] for item in document["first_process_observations"])
        and not any(item["contains_forbidden_secret"] for item in document["restart_observations"])
    )


if __name__ == "__main__":
    raise SystemExit(main())
