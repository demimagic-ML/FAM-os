#!/usr/bin/env python3
"""Capture one device-signed content-free peer qualification checkpoint."""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from tools.phase21_state_exit.console_client import PeerConsoleClient


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--installed-python", type=Path, required=True)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--device-name", required=True)
    parser.add_argument("--qualification-id", required=True)
    parser.add_argument(
        "--checkpoint",
        choices=(
            "before_remote_success", "after_remote_success",
            "before_peer_loss", "after_peer_restart",
        ),
        required=True,
    )
    parser.add_argument("--console-url", required=True)
    parser.add_argument("--console-token-file", type=Path, required=True)
    parser.add_argument("--prompt", default="Reply with exactly READY")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    _installed_imports(args.installed_python, args.repository)

    from fam_os.fabric import (
        PersistentDeviceIdentityStore,
        PhysicalPeerCheckpoint,
        create_physical_peer_observation,
        verify_physical_peer_observation,
    )
    from fam_os.schemas import dumps_document

    state_root = args.state_root.resolve()
    credentials = PersistentDeviceIdentityStore(
        state_root / "fabric/identity", os.geteuid(),
    ).resolve(args.device_name)
    token = args.console_token_file.read_text("utf-8").strip()
    context_count = len(PeerConsoleClient(
        args.console_url, token,
    ).context_evidence())
    prompt = args.prompt.encode("utf-8")
    database_paths = tuple(
        path for path in (state_root / "state").glob("fam.sqlite3*")
        if path.is_file()
    )
    checkpoint = PhysicalPeerCheckpoint(args.checkpoint)
    observation = create_physical_peer_observation(
        credentials,
        observation_id="peer-observation-" + hashlib.sha256(
            (
                args.qualification_id + "|" + checkpoint.value + "|"
                + credentials.identity.device_id
            ).encode("utf-8"),
        ).hexdigest()[:32],
        qualification_id=args.qualification_id,
        checkpoint=checkpoint,
        context_evidence_count=context_count,
        inspected_database_file_count=len(database_paths),
        prompt_sha256=hashlib.sha256(prompt).hexdigest(),
        prompt_retained=any(prompt in path.read_bytes() for path in database_paths),
        captured_at=datetime.now(UTC),
    )
    verify_physical_peer_observation(observation)
    _write_private(args.output, dumps_document(observation) + "\n")
    return 1 if observation.prompt_retained else 0


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
