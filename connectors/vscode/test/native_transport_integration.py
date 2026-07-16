#!/usr/bin/env python3
"""Cross-language proof for the TypeScript native connector wire protocol."""

import os
import socket
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from fam_os.applications import (
    ActionConfirmation,
    ActionPreparationRequest,
    ActionResult,
    ConfirmationDecision,
    ConnectorRegistration,
    ObservationRequest,
    ObservationResult,
)
from fam_os.applications.transport import (
    LocalMessage,
    LocalMessageKind,
    contract_message,
    decode_contract_message,
    receive_frame,
    send_frame,
)


ROOT = Path(__file__).parents[1]


def main() -> int:
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        os.chmod(directory, 0o700)
        path = directory / "applications.sock"
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        listener.bind(str(path))
        os.chmod(path, 0o600)
        listener.listen(1)
        listener.settimeout(10)
        process = _start_fixture(path)
        try:
            stream, _address = listener.accept()
            stream.settimeout(10)
            with stream:
                _workflow(stream)
            output, error = process.communicate(timeout=10)
        finally:
            listener.close()
            if process.poll() is None:
                process.kill()
                process.communicate()
        if process.returncode != 0:
            raise RuntimeError(
                f"native connector fixture failed: {(error or output)[-200:]}"
            )
    print("TypeScript native connector transport integration passed")
    return 0


def _workflow(stream) -> None:
    registration_message = receive_frame(stream)
    registration = decode_contract_message(registration_message)
    assert isinstance(registration, ConnectorRegistration)
    assert registration.connector_id == "fixture-connector"
    _reply(stream, registration_message, LocalMessageKind.ACK, {"accepted": True})

    observation_request = ObservationRequest(
        "observe-fixture", "fixture-instance", "vscode.editor.active", "grant-fixture"
    )
    observation_message = contract_message(
        "core-observe", LocalMessageKind.OBSERVE, observation_request
    )
    send_frame(stream, observation_message)
    observation = _receive_contract(stream, observation_message, LocalMessageKind.OBSERVATION)
    assert isinstance(observation, ObservationResult)
    assert observation.payload["language_id"] == "typescript"

    preparation = ActionPreparationRequest(
        "prepare-fixture", "fixture-instance", "vscode.workspace_edit.apply",
        "grant-fixture", "Apply fixture edit", {"fixture": True},
        "file:///fixture/example.ts", "fixture-revision-1",
    )
    prepare_message = contract_message(
        "core-prepare", LocalMessageKind.PREPARE_ACTION, preparation
    )
    send_frame(stream, prepare_message)
    proposal = _receive_contract(stream, prepare_message, LocalMessageKind.ACTION_PROPOSAL)

    confirmation = ActionConfirmation(
        "confirm-fixture", proposal.proposal_id, "grant-fixture",
        ConfirmationDecision.APPROVED, "user-fixture",
        datetime.now(timezone.utc),
    )
    confirm_message = contract_message(
        "core-confirm", LocalMessageKind.CONFIRM_ACTION, confirmation
    )
    send_frame(stream, confirm_message)
    result = _receive_contract(stream, confirm_message, LocalMessageKind.ACTION_RESULT)
    assert isinstance(result, ActionResult) and result.verified


def _receive_contract(stream, request, expected):
    message = receive_frame(stream)
    assert message.kind is expected
    assert message.correlation_id == request.message_id
    return decode_contract_message(message)


def _reply(stream, request, kind, payload) -> None:
    send_frame(stream, LocalMessage(
        "core-ack", kind, payload, correlation_id=request.message_id
    ))


def _start_fixture(path: Path):
    environment = {"PATH": os.environ.get("PATH", "")}
    return subprocess.Popen(
        ["node", "out/test-fixtures/native-connector-fixture.js", str(path)],
        cwd=ROOT,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


if __name__ == "__main__":
    raise SystemExit(main())
