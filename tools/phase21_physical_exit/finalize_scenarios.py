#!/usr/bin/env python3
"""Bind requester captures to signed peer checkpoints."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from fam_os.fabric import (
    PhysicalPeerCheckpoint,
    PhysicalPeerObservation,
    verify_physical_peer_observation,
)
from fam_os.schemas import loads_document


PROMPT_SHA256 = hashlib.sha256(b"Reply with exactly READY").hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--success-capture", type=Path, required=True)
    parser.add_argument("--loss-capture", type=Path, required=True)
    parser.add_argument("--peer-before-success", type=Path, required=True)
    parser.add_argument("--peer-after-success", type=Path, required=True)
    parser.add_argument("--peer-before-loss", type=Path, required=True)
    parser.add_argument("--peer-after-restart", type=Path, required=True)
    parser.add_argument("--success-output", type=Path, required=True)
    parser.add_argument("--loss-output", type=Path, required=True)
    args = parser.parse_args()

    success = _object(args.success_capture)
    loss = _object(args.loss_capture)
    before_success = _observation(
        args.peer_before_success, PhysicalPeerCheckpoint.BEFORE_REMOTE_SUCCESS,
    )
    after_success = _observation(
        args.peer_after_success, PhysicalPeerCheckpoint.AFTER_REMOTE_SUCCESS,
    )
    before_loss = _observation(
        args.peer_before_loss, PhysicalPeerCheckpoint.BEFORE_PEER_LOSS,
    )
    after_restart = _observation(
        args.peer_after_restart, PhysicalPeerCheckpoint.AFTER_PEER_RESTART,
    )
    observations = (before_success, after_success, before_loss, after_restart)
    qualification_ids = {
        success.get("qualification_id"), loss.get("qualification_id"),
        *(item.qualification_id for item in observations),
    }
    peer_ids = {
        success.get("peer_device_id"), loss.get("peer_device_id"),
        *(item.device_id for item in observations),
    }
    if len(qualification_ids) != 1 or len(peer_ids) != 1:
        raise ValueError("physical scenario identity binding is inconsistent")
    if any(
        item.prompt_sha256 != PROMPT_SHA256 or item.prompt_retained
        for item in observations
    ):
        raise ValueError("physical peer retained or inspected the wrong prompt")
    if not (
        before_success.captured_at <= after_success.captured_at
        <= before_loss.captured_at <= after_restart.captured_at
    ):
        raise ValueError("physical peer checkpoint ordering is invalid")
    success_delta = (
        after_success.context_evidence_count
        - before_success.context_evidence_count
    )
    loss_delta = (
        after_restart.context_evidence_count
        - before_loss.context_evidence_count
    )
    if success_delta != 1 or loss_delta != 0:
        raise ValueError("physical peer context evidence deltas are invalid")
    if loss.get("peer_authenticated_after_restart") is not True:
        raise ValueError("physical peer restart has not been authenticated")
    success["peer_context_evidence_delta"] = success_delta
    success["peer_prompt_retained"] = False
    loss["peer_context_evidence_delta"] = loss_delta
    loss["peer_prompt_retained"] = False
    _write_private(
        args.success_output, json.dumps(success, indent=2, sort_keys=True) + "\n",
    )
    _write_private(
        args.loss_output, json.dumps(loss, indent=2, sort_keys=True) + "\n",
    )
    return 0


def _observation(
    path: Path, checkpoint: PhysicalPeerCheckpoint,
) -> PhysicalPeerObservation:
    value = loads_document(path.read_text("utf-8"))
    if not isinstance(value, PhysicalPeerObservation):
        raise TypeError("physical peer checkpoint has the wrong contract")
    verify_physical_peer_observation(value)
    if value.checkpoint is not checkpoint:
        raise ValueError("physical peer checkpoint is out of sequence")
    return value


def _object(path: Path) -> dict:
    value = json.loads(path.read_text("utf-8"))
    if not isinstance(value, dict):
        raise TypeError("physical requester capture is not an object")
    return value


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
