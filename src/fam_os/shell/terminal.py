"""Small accessible command interface over the Shell controller."""

import shlex
import time
from collections.abc import Callable
from uuid import uuid4

from fam_os.shell.contracts import (
    ShellContext, ShellContextKind, ShellDecision, ShellRunState,
)
from fam_os.shell.memory_terminal import execute_memory_command
from fam_os.shell.adaptation_terminal import execute_adaptation_command
from fam_os.shell.peer_terminal import execute_peer_command
from fam_os.shell.remote_terminal import execute_remote_command
from fam_os.shell.render import render_contexts, render_snapshot


HELP = """Commands:
  Enter plain text to start a task; a selected local folder uses the engineering lifecycle
  /context add KIND RESOURCE [DISPLAY_NAME] [CAPABILITY ...]
  /context remove CONTEXT_ID
  /contexts
  /status
  /approve
  /deny
  /cancel
  /memory list [OFFSET] [LIMIT]
  /memory inspect DOCUMENT_ID
  /memory export DOCUMENT_ID
  /memory correct DOCUMENT_ID EXPECTED_SHA256 FILE --confirm
  /memory delete DOCUMENT_ID EXPECTED_SHA256 --confirm
  /memory expire GRANT_ID --confirm
  /memory receipts [OFFSET] [LIMIT]
  /adaptation status
  /adaptation snapshots|prewarms|health|drift|receipts [OFFSET] [LIMIT]
  /adaptation enable|disable|reset --confirm
  /adaptation evaluate|rollback WORKFLOW_ID --confirm
  /peer list [OFFSET] [LIMIT]
  /peer probe ENROLLMENT_ID
  /peer receipts [OFFSET] [LIMIT]
  /peer context-evidence [OFFSET] [LIMIT]
  /peer revoke ENROLLMENT_ID REVISION REASON --confirm
  /peer privacy ENROLLMENT_ID REVISION BYTES SENSITIVITIES PURPOSES WORKSPACES RAW_BOOL REASON --confirm
  /peer context ENROLLMENT EXPERT DECLARATION POLICY_REV PURPOSE WORKSPACE SENSITIVITY INTENT CAPABILITIES ASSURANCE MAX_OUTPUT
  /remote ask ENROLLMENT POLICY_REV PURPOSE WORKSPACE SENSITIVITY CONTEXT_BYTES OUTPUT_BYTES [--verify] --confirm PROMPT
  /help
  /quit
  ask [--verify] PROMPT  (compatibility alias)"""

SAFE_RUNTIME_ERRORS = {
    "shell.memory_unavailable": "Persistent memory management is unavailable.",
    "shell.memory_not_found": "That retained document or grant no longer exists.",
    "shell.memory_denied": "The persistent memory operation was not authorized.",
    "shell.memory_conflict": (
        "Persistent memory changed. Inspect it again before retrying the operation."
    ),
    "shell.adaptation_unavailable": "Live adaptation controls are unavailable.",
    "shell.adaptation_not_found": "That adaptation workflow or snapshot no longer exists.",
    "shell.adaptation_denied": "The adaptation control was not authorized.",
    "shell.adaptation_conflict": "Adaptation state changed. Inspect status and retry.",
    "shell.peer_unavailable": "Trusted peer management is unavailable.",
    "shell.peer_not_found": "That active trusted peer no longer exists.",
    "shell.peer_denied": "The peer operation was not authorized.",
    "shell.peer_conflict": "Peer state changed. List peers and retry.",
}


def _identifier() -> str:
    return str(uuid4())


class TerminalShell:
    def __init__(self, controller, context_id_factory: Callable[[], str] = _identifier):
        self._controller = controller
        self._context_id_factory = context_id_factory

    def execute(self, command_line: str) -> tuple[str, bool]:
        try:
            arguments = shlex.split(command_line)
        except ValueError:
            return "Invalid command syntax.", True
        if not arguments:
            return "", True
        raw_command = arguments[0]
        command = raw_command.removeprefix("/").casefold()
        values = arguments[1:]
        try:
            return self._dispatch(command, values, raw_command)
        except RuntimeError as error:
            if str(error) == "shell.grounding_unavailable":
                return (
                    "No active approved local source matched this request. "
                    "Approve a relevant document or folder in FAM Console and try again.",
                    True,
                )
            if str(error) in SAFE_RUNTIME_ERRORS:
                return SAFE_RUNTIME_ERRORS[str(error)], True
            return "Command could not be completed safely.", True
        except Exception:
            return "Command could not be completed safely.", True

    def _dispatch(self, command, values, raw_command):
        if command in {"quit", "exit"}:
            return "Goodbye.", False
        if command == "help":
            return HELP, True
        if command == "contexts":
            return render_contexts(self._controller.contexts()), True
        if command == "context":
            return self._context(values), True
        if command == "ask":
            return render_snapshot(self._ask(values)), True
        if command in {"refresh", "status"}:
            snapshot = self._controller.refresh() if command == "refresh" else self._controller.snapshot
            if snapshot is None:
                raise RuntimeError("no request")
            return render_snapshot(snapshot), True
        if command in {"approve", "deny"}:
            decision = ShellDecision.APPROVE if command == "approve" else ShellDecision.DENY
            return render_snapshot(self._controller.decide(decision)), True
        if command == "cancel":
            return render_snapshot(self._controller.cancel()), True
        if command == "memory":
            return execute_memory_command(self._controller, values), True
        if command == "adaptation":
            return execute_adaptation_command(self._controller, values), True
        if command == "peer":
            return execute_peer_command(self._controller, values), True
        if command == "remote":
            return render_snapshot(
                execute_remote_command(self._controller, values),
            ), True
        if raw_command.startswith("/"):
            return "Unknown command. Enter '/help' for available commands.", True
        prompt = " ".join((raw_command, *values))
        return render_snapshot(self._controller.ask(prompt)), True

    def follow(self, poll_seconds: float = .15):
        current = self._controller.snapshot
        while current is not None and current.state not in {
            ShellRunState.WAITING_APPROVAL, ShellRunState.TERMINAL,
        }:
            time.sleep(poll_seconds)
            incoming = self._controller.refresh()
            if incoming.revision != current.revision or incoming.state != current.state:
                yield render_snapshot(incoming)
            current = incoming

    def _context(self, values):
        if len(values) == 2 and values[0] == "remove":
            self._controller.remove_context(values[1])
            return "Context removed."
        if len(values) < 3 or values[0] != "add":
            raise ValueError("invalid context command")
        kind = ShellContextKind(values[1])
        resource = values[2]
        display = values[3] if len(values) > 3 else resource
        capabilities = tuple(values[4:])
        context = ShellContext(
            self._context_id_factory(), kind, resource, display, capabilities
        )
        self._controller.add_context(context)
        return f"Context added: {context.context_id}"

    def _ask(self, values):
        verification = bool(values and values[0] == "--verify")
        prompt_values = values[1:] if verification else values
        if not prompt_values:
            raise ValueError("prompt is required")
        return self._controller.ask(" ".join(prompt_values), verification)


def run_terminal(shell: TerminalShell, input_fn=input, output_fn=print) -> int:
    output_fn("FAM Shell. Enter 'help' for commands.")
    keep_running = True
    while keep_running:
        try:
            line = input_fn("fam> ")
        except (EOFError, KeyboardInterrupt):
            output_fn("Goodbye.")
            return 0
        output, keep_running = shell.execute(line)
        if output:
            output_fn(output)
        for progress in shell.follow():
            output_fn(progress)
    return 0
