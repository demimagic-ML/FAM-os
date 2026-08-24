#!/usr/bin/env python3
"""Build and qualify signed installed Phase 20.7 adaptation controls."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from tools.phase19_exit.release_environment import build_and_install
from tools.phase20_control_exit.scenario import (
    first_process_scenario,
    restarted_process_scenario,
)
from tools.phase20_control_exit.workload import OUTPUTS, PROMPTS, scripted_responses
from tools.phase20_control_exit.workload import scripted_health
from tools.phase20_live_exit.installed_service import InstalledLiveAdaptationService
from tools.phase20_live_exit.model_root import build_model_root
from tools.phase20_live_exit.scenario import inspect_state


def main() -> int:
    repository = Path(__file__).resolve().parents[1]
    output = repository / "artifacts/adaptation/phase20.7-control-and-rollback.json"
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        installation, manifest, _connector, _extensions = build_and_install(
            repository,
            root,
            "phase20-control-exit",
            "phase20-control-test",
        )
        model_root = build_model_root(root / "models")
        product_root = root / "product"
        product_root.mkdir()
        with InstalledLiveAdaptationService(
            installation,
            repository,
            product_root,
            root / "run-1",
            model_root,
            scripted_responses(),
            scripted_health(),
        ) as service:
            first = first_process_scenario(installation, repository, service)
        first_state = inspect_state(
            installation,
            repository,
            product_root,
            root / "first-state.json",
            10,
        )
        plaintext = _plaintext_found(product_root / "state/state")
        with InstalledLiveAdaptationService(
            installation,
            repository,
            product_root,
            root / "run-2",
            model_root,
            (),
        ) as restarted:
            second = restarted_process_scenario(
                installation,
                repository,
                restarted,
            )
        reset_state = inspect_state(
            installation,
            repository,
            product_root,
            root / "reset-state.json",
            10,
        )
        document = {
            "phase": "20.7",
            "release_id": manifest.release_id,
            "signer_key_id": manifest.signer_key_id,
            "release_component_count": len(manifest.components),
            "signed_install_healthy": installation.diagnose().healthy,
            "first_process": first,
            "first_shutdown_state": first_state,
            "durable_database_contains_plaintext_nonce": plaintext,
            "restarted_process": second,
            "reset_shutdown_state": reset_state,
        }
        document["passed"] = _passed(document)
        installation.remove()
        document["complete_removal"] = not installation.prefix.exists()
        document["passed"] = document["passed"] and document["complete_removal"]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    print(json.dumps(document, indent=2, sort_keys=True))
    return 0 if document["passed"] else 1


def _plaintext_found(root: Path) -> bool:
    response_content = tuple(item["content"] for item in scripted_responses())
    nonces = tuple(value.encode() for value in (*PROMPTS, *OUTPUTS, *response_content))
    return any(
        nonce in path.read_bytes()
        for path in root.glob("fam.sqlite3*")
        if path.is_file()
        for nonce in nonces
    )


def _passed(document: dict) -> bool:
    first = document["first_process"]
    second = document["restarted_process"]
    return all(
        (
            document["signed_install_healthy"],
            document["release_component_count"] == 7,
            _training_passed(first),
            _runtime_passed(first),
            _drift_passed(first),
            _control_surface_passed(first),
            _first_state_passed(document["first_shutdown_state"]),
            not document["durable_database_contains_plaintext_nonce"],
            _restart_passed(second),
            _reset_passed(second, document["reset_shutdown_state"]),
        )
    )


def _training_passed(first: dict) -> bool:
    training = first["training"]["results"]
    return bool(
        len(training) == 8
        and all(
            item["verified"] and item["status"] == "verified" for item in training[:7]
        )
        and not training[7]["verified"]
        and training[7]["status"] == "completed"
        and tuple(item["content"] for item in training) == OUTPUTS[:8]
    )


def _runtime_passed(first: dict) -> bool:
    events_before = first["events_before_disable"]
    events_after = first["events_after_disable"]
    chats = [item for item in events_after if item["kind"] == "chat"]
    prewarm_before = [item for item in events_before if item["kind"] == "prewarm"]
    prewarm_after = [item for item in events_after if item["kind"] == "prewarm"]
    return bool(
        len(chats) == 14
        and tuple(item["model_ref"] for item in chats)
        == tuple(item["model_ref"] for item in scripted_responses())
        and chats[-2]["context_tokens"] < 32768
        and chats[-1]["context_tokens"] == 32768
        and len(prewarm_before) >= 1
        and prewarm_after == prewarm_before
        and all(not item["prompt_supplied"] for item in prewarm_after)
    )


def _drift_passed(first: dict) -> bool:
    reports = first["drift_reports"]
    drifted = tuple(item for item in reports if item["drifted"])
    status = first["status_after_automatic_drift"]
    reasons = {
        "verification.quality_regressed",
        "latency.p95_regressed",
        "thermal.limit_exceeded",
        "thermal.regressed",
        "policy.violation_detected",
    }
    return bool(
        status["enabled"]
        and _same_selection(
            status["active_selections"],
            status["known_good_selections"],
        )
        and len(status["drifted_snapshot_ids"]) == 1
        and len(first["health"]) == 6
        and len(reports) == 2
        and len(drifted) == 1
        and any(not item["drifted"] for item in reports)
        and set(drifted[0]["reason_codes"]) == reasons
    )


def _control_surface_passed(first: dict) -> bool:
    shell = first["installed_shell_inspection"]
    return bool(
        shell["returncode"] == 0
        and "Adaptation drift" in shell["stdout"]
        and "Command could not be completed safely." in shell["stdout"]
        and first["disable_confirmation_denied"]
        and first["disable_receipt"]["operation"] == "disable"
        and not first["disabled_status"]["enabled"]
        and first["disabled_result"]["results"][0]["content"] == OUTPUTS[9]
        and all(first["console_assets"].values())
    )


def _first_state_passed(state: dict) -> bool:
    return bool(
        state["learning_record_count"] == 7
        and state["adaptation_snapshot_count"] >= 5
        and state["prewarm_receipt_count"] >= 1
        and state["adaptation_health_count"] == 7
        and state["adaptation_drift_report_count"] == 2
        and not state["adaptation_control_state"]["payload"]["enabled"]
        and all(item is not None for item in state["terminal_results"].values())
    )


def _restart_passed(second: dict) -> bool:
    shell = second["installed_shell_controls"]
    return bool(
        not second["before"]["status"]["enabled"]
        and len(second["before"]["drift_reports"]) == 2
        and len(second["retained_results"]["results"]) == 10
        and not second["runtime_events"]
        and shell["returncode"] == 0
        and "Adaptation: disabled" in shell["stdout"]
        and "Command could not be completed safely." in shell["stdout"]
    )


def _reset_passed(second: dict, reset: dict) -> bool:
    reset_receipt = next(
        (
            item["payload"]
            for item in reset["adaptation_control_receipts"]
            if item["payload"]["operation"] == "reset"
        ),
        None,
    )
    after = second["after_reset"]
    return bool(
        after["snapshots"] == []
        and after["prewarms"] == []
        and after["health"] == []
        and after["drift_reports"] == []
        and reset["learning_record_count"] == 0
        and reset["adaptation_snapshot_count"] == 0
        and reset["prewarm_receipt_count"] == 0
        and reset["adaptation_health_count"] == 0
        and reset["adaptation_drift_report_count"] == 0
        and len(reset["adaptation_control_receipts"]) >= 2
        and reset_receipt is not None
        and reset_receipt["removed_learning_count"] == 7
        and reset_receipt["removed_snapshot_count"] >= 5
        and reset_receipt["removed_prewarm_count"] >= 1
        and all(item is not None for item in reset["terminal_results"].values())
    )


def _same_selection(active: list[dict], known: list[dict]) -> bool:
    return {(item["workflow_id"], item["snapshot_id"]) for item in active} == {
        (item["workflow_id"], item["snapshot_id"]) for item in known
    }


if __name__ == "__main__":
    raise SystemExit(main())
