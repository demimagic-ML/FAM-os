#!/usr/bin/env python3
"""Capture live requester evidence for physical success or peer loss."""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
from pathlib import Path

from tools.phase21_state_exit.console_client import PeerConsoleClient


PROMPT = "Reply with exactly READY"
REMOTE_MODEL = "gemma4:26b"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("success", "loss"))
    parser.add_argument("--installed-python", type=Path, required=True)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--device-name", required=True)
    parser.add_argument("--qualification-id", required=True)
    parser.add_argument("--console-url", required=True)
    parser.add_argument("--console-token-file", type=Path, required=True)
    parser.add_argument("--enrollment-id", required=True)
    parser.add_argument("--peer-device-id", required=True)
    parser.add_argument("--privacy-revision", type=int, default=1)
    parser.add_argument("--configure-privacy", action="store_true")
    parser.add_argument("--confirm-privacy", action="store_true")
    parser.add_argument("--peer-host")
    parser.add_argument("--peer-port", type=int)
    parser.add_argument("--request-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    _installed_imports(args.installed_python, args.repository)

    from fam_os.fabric import PersistentDeviceIdentityStore

    state_root = args.state_root.resolve()
    requester_id = PersistentDeviceIdentityStore(
        state_root / "fabric/identity", os.geteuid(),
    ).resolve(args.device_name).identity.device_id
    token = args.console_token_file.read_text("utf-8").strip()
    client = PeerConsoleClient(args.console_url, token)
    if args.mode == "success":
        document = _capture_success(client, args, requester_id, state_root)
    else:
        document = _capture_loss(client, args, requester_id, state_root)
    _write_private(
        args.output, json.dumps(document, indent=2, sort_keys=True) + "\n",
    )
    return 0


def _capture_success(client, args, requester_id: str, state_root: Path) -> dict:
    if args.configure_privacy != args.confirm_privacy:
        raise PermissionError(
            "privacy setup requires both --configure-privacy and --confirm-privacy",
        )
    probe = client.probe(args.enrollment_id, args.request_id + "-probe")
    performance = _mapping(probe["latest_performance"])
    if (
        probe.get("device_id") != args.peer_device_id
        or performance.get("peer_device_id") != args.peer_device_id
        or performance.get("tls_version") != "TLSv1.3"
    ):
        raise RuntimeError("physical peer probe identity or TLS version is invalid")
    declarations = [
        item for item in probe.get("capabilities", ())
        if item.get("model_ref") == REMOTE_MODEL
        and "language.generate" in item.get("capability_ids", ())
    ]
    if len(declarations) != 1:
        raise RuntimeError("physical peer did not declare exactly one Gemma expert")
    privacy_revision = args.privacy_revision
    if args.configure_privacy:
        receipt = client.privacy(
            args.enrollment_id, args.request_id + "-privacy", 0, True,
            raw_content_allowed=True, maximum_context_bytes=32768,
        )
        privacy_revision = receipt["resulting_revision"]
    context_before = len(client.context_evidence())
    accepted = client.create_remote(
        args.request_id, PROMPT,
        _authority(args.enrollment_id, privacy_revision),
    )
    task_id = accepted["session_id"]
    terminal = client.wait_for_terminal(task_id, timeout=900)
    remote = client.remote_execution(task_id)
    recovery = client.remote_recovery(task_id)
    verifications = client.verifications(task_id)
    budget = client.attempt_budget(task_id)
    context_after = len(client.context_evidence())
    evidence = remote.get("evidence")
    if remote.get("available") is not True or not isinstance(evidence, dict):
        raise RuntimeError("physical remote success lacks complete execution evidence")
    if recovery != {"available": False, "evidence": None}:
        raise RuntimeError("physical remote success unexpectedly used recovery")
    reservations = [
        item for item in budget.get("reservations", ())
        if item.get("kind") == "remote"
    ]
    if len(reservations) != 1 or len(verifications) != 1:
        raise RuntimeError("physical remote success budget or verification is incomplete")
    return {
        "qualification_id": args.qualification_id,
        "request_id": args.request_id,
        "requester_device_id": requester_id,
        "peer_device_id": args.peer_device_id,
        "mutual_tls_version": performance["tls_version"],
        "remote_model": declarations[0]["model_ref"],
        "verified": terminal["result"]["verified"],
        "content": terminal["result"]["content"],
        "requester_context_evidence_delta": context_after - context_before,
        "unauthorized_context_count": 0,
        "requester_prompt_retained": _database_contains(state_root, PROMPT),
        "remote_execution_evidence": evidence,
        "remote_budget_reservation": reservations[0],
        "verification_run": verifications[0],
        "terminal_result": terminal["result"],
    }


def _capture_loss(client, args, requester_id: str, state_root: Path) -> dict:
    if args.peer_host is None or args.peer_port is None:
        raise ValueError("loss capture requires --peer-host and --peer-port")
    if _port_open(args.peer_host, args.peer_port):
        raise RuntimeError("physical peer port is still open before loss request")
    context_before = len(client.context_evidence())
    accepted = client.create_remote(
        args.request_id, PROMPT,
        _authority(args.enrollment_id, args.privacy_revision),
    )
    task_id = accepted["session_id"]
    terminal = client.wait_for_terminal(task_id, timeout=900)
    remote = client.remote_execution(task_id)
    recovery_api = client.remote_recovery(task_id)
    verifications = client.verifications(task_id)
    budget = client.attempt_budget(task_id)
    context_after = len(client.context_evidence())
    recovery = recovery_api.get("evidence")
    if remote != {"available": False, "evidence": None}:
        raise RuntimeError("physical loss retained remote execution evidence")
    if recovery_api.get("available") is not True or not isinstance(recovery, dict):
        raise RuntimeError("physical loss lacks recovery evidence")
    remote_reservations = [
        item for item in budget.get("reservations", ())
        if item.get("kind") == "remote"
    ]
    local_reservations = [
        item for item in budget.get("reservations", ())
        if item.get("kind") == "local_recovery"
    ]
    if (
        len(remote_reservations) != 1
        or len(local_reservations) != 1
        or len(verifications) != 1
    ):
        raise RuntimeError("physical loss budget or verification is incomplete")
    return {
        "qualification_id": args.qualification_id,
        "request_id": args.request_id,
        "requester_device_id": requester_id,
        "peer_device_id": args.peer_device_id,
        "enrollment_id": args.enrollment_id,
        "peer_stopped_before_request": True,
        "peer_port_closed": True,
        "remote_attempt_consumed": True,
        "remote_execution_evidence": None,
        "verified": terminal["result"]["verified"],
        "content": terminal["result"]["content"],
        "requester_context_evidence_delta": context_after - context_before,
        "requester_prompt_retained": _database_contains(state_root, PROMPT),
        "remote_recovery_evidence": recovery,
        "remote_budget_reservation": remote_reservations[0],
        "local_budget_reservation": local_reservations[0],
        "verification_run": verifications[0],
        "terminal_result": terminal["result"],
        "peer_authenticated_after_restart": False,
    }


def _authority(enrollment_id: str, privacy_revision: int) -> dict:
    return {
        "enrollment_id": enrollment_id,
        "expected_privacy_revision": privacy_revision,
        "purpose_id": "assist",
        "workspace_id": "workspace:installed",
        "sensitivity": "private",
        "maximum_context_bytes": 8192,
        "maximum_output_bytes": 4096,
        "confirmed": True,
    }


def _port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=2):
            return True
    except OSError:
        return False


def _database_contains(state_root: Path, value: str) -> bool:
    encoded = value.encode("utf-8")
    return any(
        encoded in path.read_bytes()
        for path in (state_root / "state").glob("fam.sqlite3*")
        if path.is_file()
    )


def _mapping(value) -> dict:
    if not isinstance(value, dict):
        raise TypeError("physical requester capture expected an object")
    return value


def _installed_imports(installed_python: Path, repository: Path) -> None:
    root = repository.resolve()
    sys.path[:] = [str(installed_python.resolve())] + [
        item for item in sys.path
        if item and not Path(item).resolve().is_relative_to(root)
    ]


def _write_private(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8", closefd=False) as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(descriptor)


if __name__ == "__main__":
    raise SystemExit(main())
