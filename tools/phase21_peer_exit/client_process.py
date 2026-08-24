"""Run an authenticated peer health request from installed package code."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--installed-python", type=Path, required=True)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--device-name", required=True)
    parser.add_argument("--peer-device-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    _installed_imports(args.installed_python, args.repository)
    from fam_os.fabric import (
        MutualTlsPeerClient,
        PairedPeerTrust,
        PeerControlOperation,
        PeerControlRequest,
        PersistentDeviceIdentityStore,
    )
    from fam_os.product.composition.storage_unit import ProductStorageUnit
    from fam_os.schemas import dumps_document, loads_document

    credentials = PersistentDeviceIdentityStore(
        args.state_root / "fabric/identity", os.geteuid(),
    ).resolve(args.device_name)
    storage = ProductStorageUnit(args.state_root, os.geteuid())
    try:
        opened = storage.start()
        if opened.recovery_required or storage.core is None:
            raise RuntimeError("installed peer client storage is unavailable")
        records = storage.core.repositories().peer_enrollments.active()
        trust = PairedPeerTrust(
            credentials, tuple(record.approval for record in records), str(os.geteuid()),
        )
        request = PeerControlRequest(
            "phase21-installed-health", credentials.identity.device_id,
            PeerControlOperation.HEALTH, datetime.now(UTC),
        )
        peer, payload = MutualTlsPeerClient(trust).request(
            args.peer_device_id, dumps_document(request).encode(),
        )
        response = loads_document(payload.decode())
        document = {
            "peer": asdict(peer),
            "response": json.loads(dumps_document(response))["payload"],
        }
    finally:
        storage.stop()
    args.output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    return 0


def _installed_imports(installed_python: Path, repository: Path) -> None:
    root = repository.resolve()
    sys.path[:] = [str(installed_python.resolve())] + [
        item for item in sys.path
        if item and not Path(item).resolve().is_relative_to(root)
    ]


if __name__ == "__main__":
    raise SystemExit(main())
