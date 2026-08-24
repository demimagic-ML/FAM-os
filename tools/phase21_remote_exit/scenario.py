"""Exercise a real remote expert through installed Core and Console."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools.phase21_peer_exit.installed_service import InstalledPeerService
from tools.phase21_remote_exit.database import database_observation, databases_contain
from tools.phase21_state_exit.console_client import PeerConsoleClient

OLLAMA_URL = "http://127.0.0.1:11434"
LOCAL_MODEL = "qwen3:1.7b"
REMOTE_MODEL = "gemma4:26b"
PROMPT = "Reply with exactly READY"
REMOTE_REQUEST_ID = "phase21-remote-gemma"
LOCAL_REQUEST_ID = "phase21-local-baseline"


def run_remote_scenario(
    pair, repository: Path, root: Path, paired: dict, *,
    ollama_url: str = OLLAMA_URL,
) -> dict:
    desktop_state = Path(paired["desktop_state"])
    server_state = Path(paired["server_state"])
    enrollment_id = paired["desktop_enrollment_id"]
    remote_task_id = f"task-{REMOTE_REQUEST_ID}"
    local_task_id = f"task-{LOCAL_REQUEST_ID}"
    with (
        InstalledPeerService(
            pair.desktop, desktop_state, root / "desktop-remote-run",
            ollama_url=ollama_url, model_ref=LOCAL_MODEL,
        ) as desktop,
        InstalledPeerService(
            pair.server, server_state, root / "server-remote-run",
            ollama_url=ollama_url, model_ref=REMOTE_MODEL,
        ) as server,
    ):
        try:
            desktop_client = _console(desktop)
            server_client = _console(server)
            probed = desktop_client.probe(enrollment_id, "phase21-remote-probe")
            declaration = _remote_declaration(probed["capabilities"])
            privacy = desktop_client.privacy(
                enrollment_id, "phase21-remote-privacy", 0, True,
                raw_content_allowed=True, maximum_context_bytes=32768,
            )
            before_denials = database_observation(desktop_state, ())
            server_context_before = len(server_client.context_evidence())
            denials = _denial_matrix(desktop_client, enrollment_id)
            after_denials = database_observation(desktop_state, ())
            server_context_after_denials = len(server_client.context_evidence())

            remote_accepted = desktop_client.create_remote(
                REMOTE_REQUEST_ID, PROMPT, _authority(enrollment_id),
            )
            remote_terminal = desktop_client.wait_for_terminal(
                remote_accepted["session_id"], timeout=360,
            )
            remote_verifications = desktop_client.verifications(
                remote_accepted["session_id"],
            )
            remote_execution = desktop_client.remote_execution(
                remote_accepted["session_id"],
            )
            desktop_evidence = desktop_client.context_evidence()
            server_evidence = server_client.context_evidence()
            server_context_after_remote = len(server_evidence)

            local_accepted = desktop_client.create(
                LOCAL_REQUEST_ID, PROMPT, [], [], True,
            )
            local_terminal = desktop_client.wait_for_terminal(
                local_accepted["session_id"], timeout=360,
            )
            local_remote_execution = desktop_client.remote_execution(
                local_accepted["session_id"],
            )
            server_context_after_local = len(server_client.context_evidence())
            database = database_observation(
                desktop_state, (remote_task_id, local_task_id),
            )
            evidence_contains_prompt = PROMPT in json.dumps(
                (desktop_evidence, server_evidence), sort_keys=True,
            )
        except Exception as error:
            raise RuntimeError(_service_failure(desktop, server)) from error

    core_routes = _inspect_routes(
        pair, repository, root, desktop_state, remote_task_id, local_task_id,
    )
    return {
        "ollama_url": ollama_url,
        "declared_remote_model": declaration["model_ref"],
        "declared_remote_expert": declaration["expert_id"],
        "privacy_revision": privacy["resulting_revision"],
        "denials": denials,
        "request_count_unchanged_by_denials": (
            before_denials["request_count"] == after_denials["request_count"]
        ),
        "server_context_unchanged_by_denials": (
            server_context_before == server_context_after_denials
        ),
        "remote_accepted": remote_accepted,
        "remote_terminal": remote_terminal,
        "remote_verifications": remote_verifications,
        "remote_execution": remote_execution,
        "local_accepted": local_accepted,
        "local_terminal": local_terminal,
        "local_remote_execution": local_remote_execution,
        "server_context_counts": {
            "before": server_context_before,
            "after_denials": server_context_after_denials,
            "after_remote": server_context_after_remote,
            "after_local": server_context_after_local,
        },
        "desktop_context_evidence_count": len(desktop_evidence),
        "server_context_evidence_count": len(server_evidence),
        "evidence_contains_prompt": evidence_contains_prompt,
        "database_contains_prompt": databases_contain(
            (desktop_state, server_state), (PROMPT.encode("utf-8"),),
        ),
        "database": database,
        "installed_core_routes": core_routes,
    }


def _console(service: InstalledPeerService) -> PeerConsoleClient:
    token = (service.runtime_root / "console.token").read_text().strip()
    return PeerConsoleClient(f"http://127.0.0.1:{service.port}", token)


def _remote_declaration(capabilities: list[dict]) -> dict:
    matches = tuple(
        item for item in capabilities
        if item["model_ref"] == REMOTE_MODEL
        and "language.generate" in item["capability_ids"]
    )
    if len(matches) != 1:
        raise RuntimeError("installed peer did not declare exactly one Gemma expert")
    return matches[0]


def _authority(
    enrollment_id: str,
    *,
    expected_revision: int = 1,
    workspace_id: str = "workspace:installed",
    maximum_context_bytes: int = 8192,
    confirmed: bool = True,
) -> dict:
    return {
        "enrollment_id": enrollment_id,
        "expected_privacy_revision": expected_revision,
        "purpose_id": "assist",
        "workspace_id": workspace_id,
        "sensitivity": "private",
        "maximum_context_bytes": maximum_context_bytes,
        "maximum_output_bytes": 4096,
        "confirmed": confirmed,
    }


def _denial_matrix(client: PeerConsoleClient, enrollment_id: str) -> dict[str, bool]:
    return {
        "missing_confirmation": _denied(
            client, "phase21-denied-confirmation",
            _authority(enrollment_id, confirmed=False), "403",
        ),
        "stale_privacy_revision": _denied(
            client, "phase21-denied-stale-policy",
            _authority(enrollment_id, expected_revision=2), "409",
        ),
        "unapproved_workspace": _denied(
            client, "phase21-denied-workspace",
            _authority(enrollment_id, workspace_id="workspace:other"), "403",
        ),
        "context_above_policy": _denied(
            client, "phase21-denied-context-ceiling",
            _authority(enrollment_id, maximum_context_bytes=65536), "403",
        ),
    }


def _denied(
    client: PeerConsoleClient,
    request_id: str,
    authority: dict,
    expected_status: str,
) -> bool:
    try:
        client.create_remote(request_id, PROMPT, authority)
    except RuntimeError as error:
        return expected_status in str(error)
    return False


def _service_failure(
    desktop: InstalledPeerService,
    server: InstalledPeerService,
) -> str:
    values = []
    for name, service in (("desktop", desktop), ("server", server)):
        path = service.run_root / "service.stderr"
        detail = path.read_text(errors="replace")[-12000:] if path.is_file() else ""
        values.append(f"{name} service stderr:\n{detail}")
    return "installed remote scenario failed\n" + "\n".join(values)


def _inspect_routes(
    pair,
    repository: Path,
    root: Path,
    state: Path,
    remote_task_id: str,
    local_task_id: str,
) -> dict:
    output = root / "installed-core-routes.json"
    subprocess.run((
        sys.executable,
        str(repository / "tools/phase21_remote_exit/inspect_process.py"),
        "--installed-python", str(pair.desktop.prefix / "active/python"),
        "--repository", str(repository),
        "--state-root", str(state),
        "--remote-task-id", remote_task_id,
        "--local-task-id", local_task_id,
        "--output", str(output),
    ), check=True, capture_output=True, text=True, timeout=30)
    return json.loads(output.read_text("utf-8"))
