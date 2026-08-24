"""Exercise installed fail-closed minimum-context transfer on two installations."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

from tools.phase20_management_exit.shell_client import run_installed_shell
from tools.phase21_peer_exit.installed_service import InstalledPeerService
from tools.phase21_state_exit.console_client import PeerConsoleClient


def run_context_scenario(pair, root: Path, paired: dict) -> dict:
    desktop_state = Path(paired["desktop_state"])
    server_state = Path(paired["server_state"])
    enrollment_id = paired["desktop_enrollment_id"]
    sentinels: list[str] = []
    with (
        InstalledPeerService(pair.desktop, desktop_state, root / "desktop-context-run") as desktop,
        InstalledPeerService(pair.server, server_state, root / "server-context-run") as server,
    ):
        client = _console(desktop)
        probed = client.probe(enrollment_id, "context-probe")
        declaration = next(
            item for item in probed["capabilities"] if item["capability_ids"]
        )
        privacy_one = client.privacy(
            enrollment_id, "context-privacy-one", 0, True,
        )
        descriptor = _document(
            "installed-context-descriptor", declaration, raw_fragments=[],
        )
        descriptor_evidence = client.context(enrollment_id, descriptor)
        shell = run_installed_shell(pair.desktop, desktop, (
            _shell_context(enrollment_id, declaration),
            "/peer context-evidence",
        ))
        accepted_before = _context_count(server_state)
        denials = _denial_matrix(client, enrollment_id, declaration, sentinels)
        accepted_after = _context_count(server_state)
        privacy_two = client.privacy(
            enrollment_id, "context-privacy-two", 1, True,
            raw_content_allowed=True,
        )
        allowed = "ALLOWED-EPHEMERAL-RAW-2b91f7"
        sentinels.append(allowed)
        fragment = _fragment("allowed-raw", "prompt", allowed)
        raw_evidence = client.context(enrollment_id, _document(
            "installed-context-raw", declaration, raw_fragments=[fragment],
            confirmed=True, expected_privacy_revision=2,
        ))
        desktop_evidence = client.context_evidence()
        server_evidence = _console(server).context_evidence()
        evidence_contains_raw = any(
            sentinel in json.dumps((desktop_evidence, server_evidence))
            for sentinel in sentinels
        )
    return {
        "selected_model": declaration["model_ref"],
        "selected_expert": declaration["expert_id"],
        "selected_capability_declaration": declaration["declaration_id"],
        "privacy_revision_one": privacy_one["resulting_revision"],
        "descriptor_content_bytes": descriptor_evidence["content_bytes"],
        "descriptor_receipt_verified": (
            "context.receipt_verified" in descriptor_evidence["reason_codes"]
        ),
        "installed_shell": shell,
        "denials": denials,
        "server_context_count_before_denials": accepted_before,
        "server_context_count_after_denials": accepted_after,
        "privacy_revision_two": privacy_two["resulting_revision"],
        "raw_fragment_hash_count": len(raw_evidence["raw_fragment_sha256"]),
        "desktop_evidence_count": len(desktop_evidence),
        "server_evidence_count": len(server_evidence),
        "evidence_contains_raw_content": evidence_contains_raw,
        "database_contains_context_content": _contains(
            (desktop_state, server_state), tuple(value.encode() for value in sentinels),
        ),
        "database_counts": {
            "desktop": _context_count(desktop_state),
            "server": _context_count(server_state),
        },
    }


def _console(service) -> PeerConsoleClient:
    token = (service.runtime_root / "console.token").read_text().strip()
    return PeerConsoleClient(f"http://127.0.0.1:{service.port}", token)


def _document(
    request_id, declaration, *, raw_fragments, confirmed=False,
    expected_privacy_revision=1, purpose_id="assist",
    workspace_id="workspace:installed", sensitivity="private",
):
    return {
        "request_id": request_id,
        "target_expert_id": declaration["expert_id"],
        "capability_declaration_id": declaration["declaration_id"],
        "expected_privacy_revision": expected_privacy_revision,
        "purpose_id": purpose_id, "workspace_id": workspace_id,
        "sensitivity": sensitivity, "intent_id": "intent.installed",
        "capability_ids": [declaration["capability_ids"][0]],
        "assurance_id": "verified", "maximum_output_bytes": 4096,
        "raw_fragments": raw_fragments, "confirmed": confirmed,
    }


def _fragment(identity: str, kind: str, content: str) -> dict:
    return {
        "fragment_id": identity, "kind": kind,
        "source_sha256": hashlib.sha256(("source:" + identity).encode()).hexdigest(),
        "content": content, "content_sha256": hashlib.sha256(content.encode()).hexdigest(),
    }


def _denial_matrix(client, enrollment_id, declaration, sentinels) -> dict[str, bool]:
    results = {}
    for kind in ("prompt", "file_excerpt", "memory", "retrieval"):
        sentinel = f"DENIED-{kind.upper()}-71c9e"
        sentinels.append(sentinel)
        results[kind] = _denied(client, enrollment_id, _document(
            f"denied-{kind.replace('_', '-')}", declaration,
            raw_fragments=[_fragment(kind.replace("_", "-"), kind, sentinel)],
            confirmed=True,
        ))
    for field, value in (
        ("purpose_id", "unapproved"),
        ("workspace_id", "workspace:other"),
        ("sensitivity", "restricted"),
    ):
        values = {field: value}
        results[field] = _denied(client, enrollment_id, _document(
            "denied-" + field.replace("_", "-"), declaration,
            raw_fragments=[], **values,
        ))
    altered = dict(declaration)
    altered["declaration_id"] = "capability-unapproved"
    results["capability"] = _denied(client, enrollment_id, _document(
        "denied-capability", altered, raw_fragments=[],
    ))
    return results


def _denied(client, enrollment_id, document) -> bool:
    try:
        client.context(enrollment_id, document)
    except RuntimeError as error:
        return "403" in str(error)
    return False


def _shell_context(enrollment_id, declaration) -> str:
    capability = declaration["capability_ids"][0]
    return (
        f"/peer context {enrollment_id} {declaration['expert_id']} "
        f"{declaration['declaration_id']} 1 assist workspace:installed private "
        f"intent.installed {capability} verified 4096"
    )


def _context_count(state: Path) -> int:
    connection = sqlite3.connect(state / "state/fam.sqlite3")
    try:
        return connection.execute(
            "SELECT count(*) FROM fabric_remote_context_disclosures",
        ).fetchone()[0]
    finally:
        connection.close()


def _contains(states, values) -> bool:
    return any(
        value in path.read_bytes()
        for state in states
        for path in (state / "state").glob("fam.sqlite3*")
        if path.is_file()
        for value in values
    )
