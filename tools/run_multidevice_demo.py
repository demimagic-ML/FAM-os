#!/usr/bin/env python3
import json
import base64
import socket
import threading
from dataclasses import asdict
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from cryptography.hazmat.primitives import serialization

from fam_os.fabric.demo_contracts import MultiDeviceDemoReport
from fam_os.fabric.recovery import FabricRecoveryPolicy, RemoteFailureKind
from fam_os.fabric.scheduling import FabricRouteCandidate, LatencyAwareFabricScheduler
from fam_os.fabric.transport import FabricEncryptedEnvelope, FabricSecureChannel, create_handshake


def main():
    desktop_sign, server_sign = Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate()
    desktop_eph, server_eph = X25519PrivateKey.generate(), X25519PrivateKey.generate()
    desktop = FabricSecureChannel.establish(
        "demo-session", desktop_eph, create_handshake("home-server", server_sign, server_eph),
        _public(server_sign),
    )
    server = FabricSecureChannel.establish(
        "demo-session", server_eph, create_handshake("desktop", desktop_sign, desktop_eph),
        _public(desktop_sign),
    )
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    thread = threading.Thread(target=_serve_once, args=(listener, server), daemon=True)
    thread.start()
    route = LatencyAwareFabricScheduler().decide((
        FabricRouteCandidate("laptop", "expert.local", True, 500, 0, True, True),
        FabricRouteCandidate("home-server", "expert.remote", False, 100, 20, True, True),
    ))
    with socket.create_connection(listener.getsockname()) as connection:
        request = desktop.encrypt(1, b'{"operation":"2+3","context":"redacted"}')
        connection.sendall(json.dumps(asdict(request)).encode() + b"\n")
        response = FabricEncryptedEnvelope(**json.loads(connection.makefile().readline()))
        result = json.loads(desktop.decrypt(response))
    thread.join()
    listener.close()
    recovery = FabricRecoveryPolicy().decide(RemoteFailureKind.DISCONNECTED, True)
    report = MultiDeviceDemoReport(
        "phase12-loopback-v1", ("desktop", "laptop", "home-server"), True,
        route.selected_device_id, 0, result.get("answer") == 5,
        recovery.retry_local and recovery.preserve_acceptance, True,
    )
    output = Path(__file__).parents[1] / "artifacts/fabric/phase12/multidevice-demo.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(asdict(report), indent=2, sort_keys=True) + "\n")


def _serve_once(listener, channel):
    connection, _ = listener.accept()
    with connection:
        envelope = FabricEncryptedEnvelope(**json.loads(connection.makefile().readline()))
        request = json.loads(channel.decrypt(envelope))
        answer = 5 if request["operation"] == "2+3" else None
        connection.sendall(json.dumps(asdict(channel.encrypt(2, json.dumps({"answer": answer}).encode()))).encode() + b"\n")


def _public(key):
    raw = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return base64.b64encode(raw).decode()


if __name__ == "__main__":
    main()
