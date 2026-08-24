"""Explicit confirmed terminal syntax for Core-owned remote inference."""

from fam_os.fabric import (
    RemoteContextSensitivity,
    RemoteExecutionAuthority,
)


def execute_remote_command(controller, values: list[str]):
    if len(values) < 10 or values[0].casefold() != "ask":
        raise ValueError(
            "remote ask requires enrollment, revision, scope, bounds, confirmation, and prompt",
        )
    enrollment, revision, purpose, workspace, sensitivity, context, output = values[1:8]
    options = values[8:]
    verification = bool(options and options[0] == "--verify")
    if verification:
        options = options[1:]
    if len(options) < 2 or options[0] != "--confirm":
        raise PermissionError("remote inference requires literal --confirm")
    prompt = " ".join(options[1:])
    if not prompt.strip():
        raise ValueError("remote inference prompt is required")
    authority = RemoteExecutionAuthority(
        enrollment, int(revision), purpose, workspace,
        RemoteContextSensitivity(sensitivity), int(context), int(output), True,
    )
    return controller.ask_remote(prompt, authority, verification)
