#!/usr/bin/env python3
"""Assemble and validate the final two-physical-host qualification report."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from tools.phase21_physical_exit.validation import phase21_7_passed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--requester-host", type=Path, required=True)
    parser.add_argument("--peer-host", type=Path, required=True)
    parser.add_argument("--pairing", type=Path, required=True)
    parser.add_argument("--remote-success", type=Path, required=True)
    parser.add_argument("--peer-loss-recovery", type=Path, required=True)
    parser.add_argument("--requester-diagnosis", type=Path, required=True)
    parser.add_argument("--peer-diagnosis", type=Path, required=True)
    parser.add_argument("--requester-removal", type=Path, required=True)
    parser.add_argument("--peer-removal", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    requester = _object(args.requester_host)
    peer = _object(args.peer_host)
    success = _object(args.remote_success)
    loss = _object(args.peer_loss_recovery)
    document = {
        "phase": "21.7",
        "qualification_id": _payload(requester).get("qualification_id"),
        "release_id": _payload(requester).get("release_id"),
        "signer_key_id": _payload(requester).get("signer_key_id"),
        "release_manifest_sha256": _payload(requester).get(
            "release_manifest_sha256",
        ),
        "requester_host": requester,
        "peer_host": peer,
        "pairing": _object(args.pairing),
        "remote_success": success,
        "peer_loss_recovery": loss,
        "diagnoses": _diagnoses(
            _object(args.requester_diagnosis), _object(args.peer_diagnosis),
        ),
        "removal": _removal(
            _object(args.requester_removal), _object(args.peer_removal),
        ),
        "raw_prompt_retained": any((
            success.get("requester_prompt_retained") is not False,
            success.get("peer_prompt_retained") is not False,
            loss.get("requester_prompt_retained") is not False,
            loss.get("peer_prompt_retained") is not False,
        )),
        "unauthorized_context_count": success.get(
            "unauthorized_context_count",
        ),
    }
    document["passed"] = phase21_7_passed(document)
    _write_private(
        args.output, json.dumps(document, indent=2, sort_keys=True) + "\n",
    )
    print(json.dumps({
        "output": str(args.output),
        "passed": document["passed"],
        "qualification_id": document["qualification_id"],
    }, sort_keys=True))
    return 0 if document["passed"] else 1


def _object(path: Path) -> dict:
    value = json.loads(path.read_text("utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"qualification input {path} is not a JSON object")
    return value


def _payload(value: dict) -> dict:
    payload = value.get("payload")
    if not isinstance(payload, dict):
        raise TypeError("physical host evidence has no payload object")
    return payload


def _diagnoses(requester: dict, peer: dict) -> dict:
    if requester.get("role") != "requester" or peer.get("role") != "expert_peer":
        raise ValueError("physical diagnosis roles are invalid")
    return {
        "requester_healthy": requester.get("healthy") is True,
        "peer_healthy": peer.get("healthy") is True,
    }


def _removal(requester: dict, peer: dict) -> dict:
    if requester.get("role") != "requester" or peer.get("role") != "expert_peer":
        raise ValueError("physical removal roles are invalid")
    return {
        "requester_install_absent": requester.get("install_absent") is True,
        "peer_install_absent": peer.get("install_absent") is True,
        "requester_state_absent": requester.get("state_absent") is True,
        "peer_state_absent": peer.get("state_absent") is True,
    }


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
