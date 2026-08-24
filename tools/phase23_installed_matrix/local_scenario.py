"""Real local inference and authoritative Console state from the installed Core."""

import json

from tools.phase19_exit.console_client import ConsoleClient


def run_local_scenario(service) -> dict[str, object]:
    client = _client(service)
    before = client.snapshot()
    accepted = client.create_verified(
        "phase23-local-ready", "Reply with exactly READY",
        {"kind": "exact_text", "expected_text": "READY"},
    )
    terminal = client.wait_for_terminal(accepted["session_id"], timeout=360)
    runs = client.verifications(accepted["session_id"])
    after = client.snapshot()
    result = terminal.get("result") or {}
    release = json.loads(
        (service.installation.prefix / "active/release-manifest.json").read_text(),
    )["payload"]["release_id"]
    live_state = _live_state(before, after, release)
    passed = all((
        result.get("status") == "verified",
        result.get("content") == "READY",
        bool(runs),
        all(item.get("effective_trust") == "signed" for item in runs),
        live_state["passed"],
    ))
    return {
        "accepted": accepted, "terminal": terminal,
        "verification_runs": runs, "console_live_state": live_state,
        "passed": passed,
    }


def _client(service) -> ConsoleClient:
    token = (service.runtime_root / "console.token").read_text().strip()
    return ConsoleClient(f"http://127.0.0.1:{service.port}", token)


def _live_state(before: dict, after: dict, release_id: str) -> dict[str, object]:
    before_items = _items(before)
    after_items = _items(after)
    terminal_before = int(before_items[("audit", "terminal-results")]["value"])
    terminal_after = int(after_items[("audit", "terminal-results")]["value"])
    resident_after = int(after_items[("experts", "resident")]["value"])
    enabled_after = int(after_items[("experts", "enabled")]["value"])
    signed_after = int(after_items[("experts", "signed")]["value"])
    active_grants = int(after_items[("permissions", "application-grants")]["value"])
    action_records = int(after_items[("audit", "application-actions")]["value"])
    resources = {
        key: after_items[("resources", key)]["value"]
        for key in ("cpu", "memory", "vram", "storage", "policy")
    }
    passed = all((
        before.get("release_id") == release_id,
        after.get("release_id") == release_id,
        terminal_after == terminal_before + 1,
        resident_after >= 1,
        enabled_after >= 1,
        signed_after >= 1,
        active_grants >= 0,
        action_records >= 0,
        after_items[("memory", "session")]["value"] == "Enabled",
        after_items[("recovery", "mode")]["value"] == "Ready",
        after.get("recovery_mode") is False,
        all(value for value in resources.values()),
        all(
            item.get("status") != "unavailable"
            for section in after.get("sections", ())
            for item in section.get("items", ())
        ),
    ))
    return {
        "release_id": after.get("release_id"),
        "terminal_results_before": terminal_before,
        "terminal_results_after": terminal_after,
        "resident_models_after": resident_after,
        "enabled_experts_after": enabled_after,
        "signed_bindings_after": signed_after,
        "active_application_grants": active_grants,
        "verified_application_actions": action_records,
        "session_memory": after_items[("memory", "session")]["value"],
        "recovery_mode": after.get("recovery_mode"),
        "resources": resources,
        "passed": passed,
    }


def _items(snapshot: dict) -> dict[tuple[str, str], dict]:
    return {
        (section["section_id"], item["item_id"]): item
        for section in snapshot.get("sections", ())
        for item in section.get("items", ())
    }
