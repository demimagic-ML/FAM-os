"""Desktop notification adapter using Omarchy's stable command when available."""

from __future__ import annotations

import shutil

from fam_os.adapters.omarchy.commands import OmarchyCommandRunner, CommandReceipt


def send_notification(
    title: str, message: str, *, runner=None, which=shutil.which,
) -> CommandReceipt:
    if not title.strip() or not message.strip():
        raise ValueError("notification title and message are required")
    executable = which("omarchy-notification-send") or which("notify-send")
    if executable is None:
        return CommandReceipt(("notification",), 127, "", "notification command unavailable")
    return (runner or OmarchyCommandRunner()).run((executable, title, message))
