"""Desktop notification adapter using Omarchy's stable command when available."""

from __future__ import annotations

import shutil

from fam_os.adapters.omarchy.commands import OmarchyCommandRunner, CommandReceipt


def send_notification(
    title: str, message: str, *, urgency: str = "normal",
    icon: str = "fam-os", replace_id: int | None = None,
    print_id: bool = False, click_command: tuple[str, ...] = ("fam", "console"),
    runner=None, which=shutil.which,
) -> CommandReceipt:
    if not title.strip() or not message.strip():
        raise ValueError("notification title and message are required")
    if urgency not in {"low", "normal", "critical"}:
        raise ValueError("notification urgency is invalid")
    executable = which("omarchy") or which("omarchy-notification-send")
    if executable is not None:
        prefix = (
            (executable, "notification", "send")
            if executable.endswith("omarchy")
            else (executable,)
        )
        command = [
            *prefix, "--app-name", "FAM", "-u", urgency, "-i", icon,
        ]
        if replace_id is not None:
            command.extend(("-r", str(replace_id)))
        if print_id:
            command.append("-p")
        command.extend((title, message))
        if click_command:
            command.extend(("--exec", *click_command))
        return (runner or OmarchyCommandRunner()).run(tuple(command))
    executable = which("notify-send")
    if executable is None:
        return CommandReceipt(("notification",), 127, "", "notification command unavailable")
    return (runner or OmarchyCommandRunner()).run((
        executable, "--app-name=FAM", f"--urgency={urgency}",
        f"--icon={icon}", title, message,
    ))
