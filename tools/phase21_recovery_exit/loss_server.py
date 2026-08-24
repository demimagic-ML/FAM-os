"""Authenticate and receive one remote request, then observe requester loss."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import sys
from dataclasses import asdict
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--installed-python", type=Path, required=True)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--device-name", required=True)
    parser.add_argument("--listen-host", required=True)
    parser.add_argument("--listen-port", type=int, required=True)
    parser.add_argument("--ready-file", type=Path, required=True)
    parser.add_argument("--received-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    _installed_imports(args.installed_python, args.repository)

    from fam_os.fabric import PairedPeerTrust, PersistentDeviceIdentityStore
    from fam_os.fabric.tls_transport import MAX_PEER_FRAME_BYTES, read_frame
    from fam_os.product.composition.storage_unit import ProductStorageUnit

    credentials = PersistentDeviceIdentityStore(
        args.state_root / "fabric/identity", os.geteuid(),
    ).resolve(args.device_name)
    storage = ProductStorageUnit(args.state_root, os.geteuid())
    try:
        opened = storage.start()
        if opened.recovery_required or storage.core is None:
            raise RuntimeError("installed loss server storage is unavailable")
        approvals = tuple(
            record.approval
            for record in storage.core.repositories().peer_enrollments.active()
        )
        trust = PairedPeerTrust(credentials, approvals, str(os.geteuid()))
    finally:
        storage.stop()

    listener = socket.socket()
    try:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((args.listen_host, args.listen_port))
        listener.listen(1)
        listener.settimeout(30)
        args.ready_file.write_text("ready\n", encoding="utf-8")
        connection, _ = listener.accept()
        with connection:
            connection.settimeout(60)
            with trust.server_context().wrap_socket(
                connection, server_side=True,
            ) as secured:
                peer = trust.authenticate(secured)
                request = read_frame(secured, MAX_PEER_FRAME_BYTES)
                args.received_file.write_text("received\n", encoding="utf-8")
                loss_observed = False
                try:
                    loss_observed = secured.recv(1) == b""
                except OSError:
                    loss_observed = True
        document = {
            "authenticated_peer": asdict(peer),
            "request_content_bytes": len(request),
            "request_sha256": hashlib.sha256(request).hexdigest(),
            "response_bytes_sent": 0,
            "requester_loss_observed": loss_observed,
        }
        args.output.write_text(
            json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8",
        )
    finally:
        listener.close()
    return 0


def _installed_imports(installed_python: Path, repository: Path) -> None:
    root = repository.resolve()
    sys.path[:] = [str(installed_python.resolve())] + [
        item for item in sys.path
        if item and not Path(item).resolve().is_relative_to(root)
    ]


if __name__ == "__main__":
    raise SystemExit(main())
