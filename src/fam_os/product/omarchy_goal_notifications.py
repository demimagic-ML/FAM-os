"""Actionable, de-duplicated Omarchy notifications for durable goals."""

from __future__ import annotations

import json
import os
from pathlib import Path

from fam_os.adapters.omarchy.notifications import send_notification


class OmarchyGoalNotifications:
    def __init__(self, state_path: Path, *, sender=send_notification) -> None:
        self._state_path = state_path
        self._sender = sender

    def __call__(
        self, goal_id: str, status: str, title: str, detail: str = "",
        *, recovery_attempt: int = 0,
    ) -> None:
        if status == "retry_wait" and recovery_attempt < 3:
            return
        presentation = {
            "completed": ("normal", "FAM completed the goal", detail or title),
            "failed": ("critical", "FAM needs attention", detail or title),
            "waiting_approval": (
                "normal", "FAM is ready to apply changes", detail or title,
            ),
            "retry_wait": (
                "normal", "FAM is recovering",
                detail or f"Attempt {recovery_attempt} for {title}",
            ),
        }.get(status)
        if presentation is None:
            return
        values = self._read()
        replace = values.get(goal_id)
        urgency, headline, message = presentation
        receipt = self._sender(
            headline, message, urgency=urgency,
            replace_id=replace if isinstance(replace, int) else None,
            print_id=True,
        )
        if not receipt.succeeded:
            return
        identifier = _notification_id(receipt.stdout)
        if identifier is not None:
            values[goal_id] = identifier
            self._write(values)

    def _read(self) -> dict[str, int]:
        try:
            value = json.loads(self._state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        if not isinstance(value, dict):
            return {}
        return {
            str(key): item for key, item in value.items()
            if isinstance(item, int) and not isinstance(item, bool) and item > 0
        }

    def _write(self, value: dict[str, int]) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self._state_path.parent, 0o700)
        if self._state_path.is_symlink():
            raise PermissionError("notification state cannot be a symbolic link")
        temporary = self._state_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(value, sort_keys=True) + "\n")
        os.chmod(temporary, 0o600)
        os.replace(temporary, self._state_path)


def _notification_id(value: str) -> int | None:
    for token in reversed(value.split()):
        if token.isdigit() and int(token) > 0:
            return int(token)
    return None
