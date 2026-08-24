import socket
import threading
import time
from datetime import datetime, timezone

from fam_os.applications import (
    ActionProposal,
    ActionResult,
    ActionStatus,
    ApplicationAuthority,
    ApplicationIdentity,
    ApplicationInstance,
    CapabilityDescriptor,
    CapabilityKind,
    CapabilityRegistryEntry,
    ConditionEvidence,
    ConditionRequirement,
    ConfirmationPolicy,
    ConnectorRegistration,
    ConnectorTransportKind,
    ObservationResult,
    ObservationStatus,
    Reversibility,
)
from fam_os.applications.transport import (
    LocalMessageKind,
    contract_message,
    decode_contract_message,
    receive_frame,
    send_frame,
)
from fam_os.shell import ShellAskCommand, ShellContext, ShellContextKind
from fam_os.core.ports import InferenceResponse
from fam_os.telemetry import InferenceMetrics
from tests.integration.product_runtime_fixture import ResidentRuntimeFixture


BEFORE = "vscode-document:1:" + "a" * 64
AFTER = "vscode-document:2:" + "b" * 64


class CountingRuntime(ResidentRuntimeFixture):
    def __init__(self):
        super().__init__()
        self.calls = []

    def chat(self, request):
        self.calls.append(request)
        return InferenceResponse(
            '{"document_uri":"file:///workspace/main.py","edits":[]}',
            InferenceMetrics(request.model_ref, 0.01, 0.0, 8, 4, 400.0),
        )

class ActionConnector:
    def __init__(self, path):
        self.path = path
        self.registered = threading.Event()
        self.executed = threading.Event()
        self.reversed = threading.Event()
        self.mutated = False
        self.preparations = []
        self._prepared_capability = None
        self._prepared_proposal_id = None
        self._undo_proposals = 0
        self._stream = None
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def close(self):
        if self._stream is not None:
            try:
                self._stream.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self._stream.close()
        self._thread.join(timeout=2)

    def _run(self):
        stream = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._stream = stream
        stream.connect(str(self.path))
        send_frame(stream, contract_message(
            "register-action", LocalMessageKind.REGISTER, registration(),
        ))
        receive_frame(stream)
        self.registered.set()
        try:
            while True:
                self._dispatch(stream, receive_frame(stream))
        except (EOFError, OSError):
            pass

    def _dispatch(self, stream, message):
        value = decode_contract_message(message)
        if message.kind is LocalMessageKind.OBSERVE:
            response = ObservationResult(
                value.request_id, ObservationStatus.OBSERVED,
                datetime.now(timezone.utc), {"document_uri": value.resource_uri},
                value.resource_uri, AFTER if self.mutated else BEFORE,
            )
            kind = LocalMessageKind.OBSERVATION
        elif message.kind is LocalMessageKind.PREPARE_ACTION:
            self.preparations.append(value)
            self._prepared_capability = value.capability_id
            if value.capability_id == "vscode.workspace_edit.undo":
                self._undo_proposals += 1
                proposal_id = f"proposal-undo-{self._undo_proposals}"
            else:
                proposal_id = "proposal-live"
            self._prepared_proposal_id = proposal_id
            conditions = (
                ConditionRequirement("document.hash", "sha256", "Hash matches."),
                ConditionRequirement(
                    "document.version", "vscode.document-version", "Version matches.",
                ),
            )
            response = ActionProposal(
                proposal_id, value, {"edits": 0}, Reversibility.REVERSIBLE,
                ConfirmationPolicy.ALWAYS, conditions, conditions,
                "vscode.workspace_edit.undo",
            )
            kind = LocalMessageKind.ACTION_PROPOSAL
        elif message.kind is LocalMessageKind.CONFIRM_ACTION:
            response = self._execute()
            kind = LocalMessageKind.ACTION_RESULT
        else:
            return
        send_frame(stream, contract_message(
            f"response-{message.message_id}", kind, response, message.message_id,
        ))

    def _execute(self):
        undoing = self._prepared_capability == "vscode.workspace_edit.undo"
        self.mutated = not undoing
        revision = BEFORE if undoing else AFTER
        evidence = (
            ConditionEvidence("document.hash", "sha256", True, revision),
            ConditionEvidence(
                "document.version", "vscode.document-version", True, revision,
            ),
        )
        if undoing:
            self.reversed.set()
        else:
            self.executed.set()
        return ActionResult(
            self._prepared_proposal_id, ActionStatus.VERIFIED,
            datetime.now(timezone.utc), evidence, {"applied_edits": 0},
            AFTER if undoing else BEFORE, revision,
            "redo-live" if undoing else "undo-live",
        )

def registration():
    application = ApplicationIdentity("com.microsoft.vscode", "Visual Studio Code")
    instance = ApplicationInstance(
        "instance-action", application, "connector-action",
        workspace_uris=("file:///workspace/",),
    )
    observe = CapabilityDescriptor(
        "vscode.editor.active", "Observe editor", "Observe editor revision.",
        CapabilityKind.OBSERVATION, ApplicationAuthority.OBSERVE,
        "vscode.editor.active.input.v1", "vscode.editor.active.output.v1",
    )
    actions = tuple(
        CapabilityDescriptor(
            capability_id, display_name, description,
            CapabilityKind.ACTION, ApplicationAuthority.MODIFY,
            "vscode.workspace_edit.input.v1", "vscode.workspace_edit.output.v1",
            Reversibility.REVERSIBLE, ConfirmationPolicy.ALWAYS,
            ("document.hash", "document.version"),
        )
        for capability_id, display_name, description in (
            ("vscode.workspace_edit.apply", "Apply edit", "Apply reversible edit."),
            ("vscode.workspace_edit.undo", "Undo edit", "Reverse an applied edit."),
        )
    )
    entries = tuple(
        CapabilityRegistryEntry(
            f"entry-{index}", "connector-action", "instance-action",
            application.application_id, capability, ("file:///workspace/",),
        )
        for index, capability in enumerate((observe, *actions), 1)
    )
    return ConnectorRegistration(
        "connector-action", ConnectorTransportKind.NATIVE_LOCAL,
        "fam.native-connector", "1", instance, entries,
        datetime.now(timezone.utc),
    )


def command():
    return ShellAskCommand(
        "action-request", "Apply the requested edit in the active file.",
        (
            ShellContext(
                "application", ShellContextKind.APPLICATION,
                "instance-action", "Visual Studio Code",
                ("vscode.editor.active", "vscode.workspace_edit.apply"),
            ),
            ShellContext(
                "resource", ShellContextKind.FILE,
                "file:///workspace/main.py", "main.py",
            ),
        ),
    )


def approval(client, session_id):
    deadline = time.monotonic() + 5
    snapshot = None
    while time.monotonic() < deadline:
        snapshot = client.snapshot(session_id)
        if snapshot.approval is not None:
            return snapshot
        time.sleep(0.01)
    raise AssertionError(f"application action did not request approval: {snapshot!r}")


def terminal(client, session_id):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        snapshot = client.snapshot(session_id)
        if snapshot.result is not None:
            return snapshot
        time.sleep(0.01)
    raise AssertionError("application action did not become terminal")
