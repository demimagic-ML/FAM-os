"""Thin owner CLI operations for explicit peer pairing and enrollment."""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from fam_os.fabric import (
    DevicePairingOffer,
    PeerEndpoint,
    PeerServiceConfiguration,
    PersistentDeviceIdentityStore,
    confirm_pairing,
    create_pairing_offer,
    pairing_code,
    verify_pairing_offer,
)
from fam_os.product.composition.storage_unit import ProductStorageUnit
from fam_os.product.owner_identity import local_owner_id
from fam_os.product.peer_configuration import PeerConfigurationStore
from fam_os.schemas import dumps_document, loads_document


def run_peer_command(args) -> int:
    state_root = args.state_root.absolute()
    configuration_store = PeerConfigurationStore(
        state_root / "config/peer.json", os.geteuid(),
    )
    configuration = configuration_store.load()
    if args.peer_action == "configure":
        if not args.confirm:
            raise PermissionError("peer listener configuration requires --confirm")
        configuration = PeerServiceConfiguration(
            True, args.device_name or configuration.display_name,
            args.listen_host, args.listen_port,
            PeerEndpoint(args.advertised_host, args.advertised_port),
        )
        configuration_store.put(configuration)
        print(dumps_document(configuration))
        return 0
    credentials = PersistentDeviceIdentityStore(
        state_root / "fabric/identity", os.geteuid(),
    ).resolve(args.device_name or configuration.display_name)
    if args.peer_action == "identity":
        print(json.dumps(asdict(credentials.identity), sort_keys=True))
        return 0
    if args.peer_action == "offer":
        endpoint = (
            PeerEndpoint(args.host, args.port)
            if args.host is not None and args.port is not None
            else configuration.advertised_endpoint
        )
        if endpoint is None:
            raise ValueError("peer offer needs --host/--port or saved listener configuration")
        offer = create_pairing_offer(
            credentials, endpoint,
        )
        print(dumps_document(offer))
        return 0
    local = _offer(args.local_offer)
    peer = _offer(args.peer_offer)
    now = datetime.now(UTC)
    verify_pairing_offer(local, observed_at=now)
    verify_pairing_offer(peer, observed_at=now)
    code = pairing_code(local, peer)
    if args.peer_action == "code":
        print(json.dumps({
            "local_device_id": local.identity.device_id,
            "peer_device_id": peer.identity.device_id,
            "pairing_code": code,
        }, sort_keys=True))
        return 0
    if not args.confirm:
        raise PermissionError("peer approval requires --confirm after comparing the code")
    approval = confirm_pairing(
        credentials, local, peer, args.code,
        owner_id=local_owner_id(os.geteuid()), approved_at=now,
    )
    storage = ProductStorageUnit(state_root, os.geteuid())
    try:
        opened = storage.start()
        if opened.recovery_required or storage.core is None:
            raise RuntimeError("peer enrollment is unavailable while product storage needs recovery")
        record = storage.core.repositories().peer_enrollments.enroll(approval)
        print(dumps_document(record))
    finally:
        storage.stop()
    return 0


def _offer(path: Path) -> DevicePairingOffer:
    value = loads_document(path.read_text("utf-8"))
    if not isinstance(value, DevicePairingOffer):
        raise TypeError("pairing input is not a device pairing offer")
    return value
