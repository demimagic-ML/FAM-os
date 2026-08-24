#!/usr/bin/env python3
"""Derive reciprocal physical pairing evidence from signed enrollments."""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
from pathlib import Path

from fam_os.fabric import (
    PeerEnrollmentRecord,
    verify_pairing_approval,
)
from fam_os.schemas import loads_document


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--requester-enrollment", type=Path, required=True)
    parser.add_argument("--peer-enrollment", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    requester = _enrollment(args.requester_enrollment)
    peer = _enrollment(args.peer_enrollment)
    document = pairing_document(requester, peer)
    _write_private(
        args.output, json.dumps(document, indent=2, sort_keys=True) + "\n",
    )
    return 0


def pairing_document(
    requester: PeerEnrollmentRecord, peer: PeerEnrollmentRecord,
) -> dict:
    requester_approval = requester.approval
    peer_approval = peer.approval
    verify_pairing_approval(
        requester_approval, requester_approval.local_identity,
    )
    verify_pairing_approval(peer_approval, peer_approval.local_identity)
    requester_id = requester_approval.local_identity.device_id
    peer_id = peer_approval.local_identity.device_id
    if (
        not requester.active
        or not peer.active
        or requester_id != peer_approval.peer_identity.device_id
        or peer_id != requester_approval.peer_identity.device_id
        or requester_approval.ceremony_sha256
        != peer_approval.ceremony_sha256
        or _loopback(requester_approval.peer_endpoint.host)
        or _loopback(peer_approval.peer_endpoint.host)
    ):
        raise ValueError("physical pairing enrollments are not reciprocal and active")
    return {
        "requester_device_id": requester_id,
        "peer_device_id": peer_id,
        "pairing_codes_match": True,
        "requester_enrollment_active": True,
        "peer_enrollment_active": True,
        "requester_enrollment_id": requester.enrollment_id,
        "peer_enrollment_id": peer.enrollment_id,
        "ceremony_sha256": requester_approval.ceremony_sha256,
    }


def _enrollment(path: Path) -> PeerEnrollmentRecord:
    value = loads_document(path.read_text("utf-8"))
    if not isinstance(value, PeerEnrollmentRecord):
        raise TypeError("physical pairing input is not an enrollment record")
    return value


def _loopback(host: str) -> bool:
    if host.casefold() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


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
