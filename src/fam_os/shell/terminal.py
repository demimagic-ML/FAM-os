"""Small accessible command interface over the Shell controller."""

import shlex
from collections.abc import Callable
from uuid import uuid4

from fam_os.shell.contracts import ShellContext, ShellContextKind, ShellDecision
from fam_os.shell.render import render_contexts, render_snapshot


HELP = """Commands:
  context add KIND RESOURCE [DISPLAY_NAME] [CAPABILITY ...]
  context remove CONTEXT_ID
  contexts
  ask [--verify] PROMPT
  refresh
  status
  approve
  deny
  cancel
  help
  quit"""


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
        command, values = arguments[0].casefold(), arguments[1:]
        try:
            return self._dispatch(command, values)
        except Exception:
            return "Command could not be completed safely.", True

    def _dispatch(self, command, values):
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
        return "Unknown command. Enter 'help' for available commands.", True

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
    return 0
