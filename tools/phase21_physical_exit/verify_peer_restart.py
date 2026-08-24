#!/usr/bin/env python3
"""Verify the lost physical peer is authenticated again after restart."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from tools.phase21_state_exit.console_client import PeerConsoleClient


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--loss-capture", type=Path, required=True)
    parser.add_argument("--console-url", required=True)
    parser.add_argument("--console-token-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    document = _object(args.loss_capture)
    token = args.console_token_file.read_text("utf-8").strip()
    probe = PeerConsoleClient(args.console_url, token).probe(
        document["enrollment_id"], document["request_id"] + "-restart-probe",
    )
    performance = probe.get("latest_performance")
    if not isinstance(performance, dict) or (
        probe.get("device_id") != document["peer_device_id"]
        or performance.get("peer_device_id") != document["peer_device_id"]
        or performance.get("tls_version") != "TLSv1.3"
    ):
        raise RuntimeError("restarted physical peer authentication failed")
    document["peer_authenticated_after_restart"] = True
    document.pop("enrollment_id", None)
    _write_private(
        args.output, json.dumps(document, indent=2, sort_keys=True) + "\n",
    )
    return 0


def _object(path: Path) -> dict:
    value = json.loads(path.read_text("utf-8"))
    if not isinstance(value, dict):
        raise TypeError("physical peer loss capture is not an object")
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
