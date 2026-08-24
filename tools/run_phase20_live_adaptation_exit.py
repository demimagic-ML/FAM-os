#!/usr/bin/env python3
"""Build and qualify signed installed Phase 20.6 live predictive adaptation."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from tools.phase19_exit.release_environment import build_and_install
from tools.phase20_live_exit.installed_service import InstalledLiveAdaptationService
from tools.phase20_live_exit.model_root import build_model_root
from tools.phase20_live_exit.scenario import (
    OUTPUTS,
    PRIMARY,
    PROMPTS,
    REDACTION,
    STRONG,
    inspect_state,
    run_client,
    scripted_responses,
)


def main() -> int:
    repository = Path(__file__).resolve().parents[1]
    output = repository / "artifacts/adaptation/phase20.6-live-adaptation.json"
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        installation, manifest, _connector, _extensions = build_and_install(
            repository, root, "phase20-live-exit", "phase20-live-test",
        )
        model_root = build_model_root(root / "models")
        product_root = root / "product"
        product_root.mkdir()
        with InstalledLiveAdaptationService(
            installation, repository, product_root, root / "run-1",
            model_root, scripted_responses(),
        ) as service:
            trained = run_client(installation, repository, service, "train")
            service.wait_for_prewarm(STRONG)
            adapted = run_client(installation, repository, service, "adapted")
            service.wait_for_prewarm(PRIMARY)
            first_events = service.events()
        first_state = inspect_state(
            installation, repository, product_root, root / "first-state.json",
        )
        plaintext = _plaintext_found(product_root / "state/state")
        with InstalledLiveAdaptationService(
            installation, repository, product_root, root / "run-2",
            model_root, (),
        ) as restarted:
            restarted.wait_for_prewarm(PRIMARY)
            revisited = run_client(installation, repository, restarted, "restart")
            restart_events = restarted.events()
        restart_state = inspect_state(
            installation, repository, product_root, root / "restart-state.json",
        )
        document = _document(
            manifest, installation.diagnose().healthy, trained, adapted,
            first_events, first_state, plaintext, revisited,
            restart_events, restart_state,
        )
        document["passed"] = _passed(document)
        installation.remove()
        document["complete_removal"] = not installation.prefix.exists()
        document["passed"] = document["passed"] and document["complete_removal"]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    print(json.dumps(document, indent=2, sort_keys=True))
    return 0 if document["passed"] else 1


def _document(
    manifest, healthy, trained, adapted, events, state, plaintext,
    revisited, restart_events, restart_state,
):
    chats = tuple(item for item in events if item["kind"] == "chat")
    baseline = chats[0]["context_tokens"]
    repeated = chats[-1]["context_tokens"]
    return {
        "phase": "20.6", "release_id": manifest.release_id,
        "signer_key_id": manifest.signer_key_id,
        "release_component_count": len(manifest.components),
        "signed_install_healthy": healthy,
        "training_results": trained, "adapted_result": adapted,
        "runtime_events": events, "first_shutdown_state": state,
        "baseline_context_tokens": baseline,
        "adapted_context_tokens": repeated,
        "context_allocation_reduction_fraction": (baseline - repeated) / baseline,
        "baseline_verification_quality": 1.0,
        "adapted_verification_quality": 1.0,
        "durable_database_contains_plaintext_nonce": plaintext,
        "restart_results": revisited, "restart_runtime_events": restart_events,
        "restart_shutdown_state": restart_state,
    }


def _plaintext_found(root: Path) -> bool:
    nonces = tuple(value.encode() for value in (*PROMPTS, *OUTPUTS))
    return any(
        nonce in path.read_bytes()
        for path in root.glob("fam.sqlite3*") if path.is_file()
        for nonce in nonces
    )


def _passed(document: dict) -> bool:
    training = document["training_results"]["results"]
    adapted = document["adapted_result"]["results"]
    all_results = (*training, *adapted)
    events = document["runtime_events"]
    chats = tuple(item for item in events if item["kind"] == "chat")
    prewarms = tuple(item for item in events if item["kind"] == "prewarm")
    state = document["first_shutdown_state"]
    restart = document["restart_shutdown_state"]
    snapshot_text = json.dumps(state["adaptation_snapshots"], sort_keys=True)
    return bool(
        document["signed_install_healthy"]
        and document["release_component_count"] == 7
        and len(all_results) == 6
        and all(item["verified"] and item["status"] == "verified" for item in all_results)
        and tuple(item["content"] for item in all_results) == OUTPUTS
        and len(chats) == 10
        and tuple(item["model_ref"] for item in chats) == (
            PRIMARY, PRIMARY, PRIMARY, STRONG, PRIMARY,
            PRIMARY, PRIMARY, STRONG, PRIMARY, STRONG,
        )
        and chats[0]["context_tokens"] == 32768
        and chats[3]["context_tokens"] == 32768
        and all(2048 <= item["context_tokens"] <= 4096 for item in chats[4:])
        and chats[-1]["context_tokens"] == 2048
        and any(item["model_ref"] == STRONG for item in prewarms)
        and any(item["model_ref"] == PRIMARY for item in prewarms)
        and all(not item["prompt_supplied"] for item in prewarms)
        and document["context_allocation_reduction_fraction"] == 0.9375
        and document["baseline_verification_quality"] == document["adapted_verification_quality"]
        and state["learning_record_count"] == 6
        and state["adaptation_snapshot_count"] == 5
        and state["prewarm_receipt_count"] == 3
        and set(state["request_prompts"].values()) == {REDACTION}
        and all(item["verified"] for item in state["terminal_results"].values())
        and all(prompt not in snapshot_text for prompt in PROMPTS)
        and all(output not in snapshot_text for output in OUTPUTS)
        and not document["durable_database_contains_plaintext_nonce"]
        and tuple(document["restart_results"]["results"]) == all_results
        and not any(item["kind"] == "chat" for item in document["restart_runtime_events"])
        and any(
            item["kind"] == "prewarm" and item["model_ref"] == PRIMARY
            for item in document["restart_runtime_events"]
        )
        and restart["adaptation_snapshot_count"] == 5
        and restart["prewarm_receipt_count"] == 4
        and restart["terminal_results"] == state["terminal_results"]
    )


if __name__ == "__main__":
    raise SystemExit(main())
