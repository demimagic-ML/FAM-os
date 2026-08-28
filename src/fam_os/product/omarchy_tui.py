"""Interactive terminal surface for Omarchy's coding-agent contract."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from fam_os.product.omarchy_agent_client import (
    submit_from_omarchy,
    widget_request,
)


_TERMINAL = {"completed", "failed", "cancelled"}


def run_omarchy_tui(
    workspace: Path,
    *,
    authority_profile: str,
    runtime_root: Path,
    source: str = "omarchy-scratchpad",
    initial_goal: bool = False,
    read=input,
    write=print,
) -> int:
    canonical = workspace.resolve(strict=True)
    goal_mode = initial_goal
    write(f"FAM — {canonical}")
    initial = _show_status(runtime_root, write, quiet=True)
    provider = str(initial.get("engineeringProvider") or "automatic")
    write(
        f"Provider: {provider} · Authority: {authority_profile}"
        f" · Mode: {'goal' if goal_mode else 'chat'}"
    )
    write(
        "Type /help for commands. The full Console remains available with /console.\n"
    )
    goal = initial.get("goal")
    if isinstance(goal, dict):
        write(_goal_line(goal))
    while True:
        try:
            value = read("goal › " if goal_mode else "fam › ").strip()
        except (EOFError, KeyboardInterrupt):
            write("")
            return 0
        if not value:
            continue
        command, separator, content = value.partition(" ")
        if command in {"/quit", "/exit"}:
            return 0
        if command == "/help":
            write(
                "/chat  ordinary requests · /goal [request]  durable Goal Mode\n"
                "/status  compact live activity · /watch  follow the active goal\n"
                "/pause · /resume · /cancel · /guide <text>\n"
                "/candidate · /console · /quit"
            )
            continue
        if command == "/chat":
            goal_mode = False
            if not content:
                write("Chat mode enabled.")
                continue
            value = content
        elif command == "/goal":
            goal_mode = True
            if not content:
                write("Goal Mode enabled. The next request starts a durable goal.")
                continue
            value = content
        elif command == "/status":
            _show_status(runtime_root, write)
            continue
        elif command == "/watch":
            _watch(runtime_root, write)
            continue
        elif command in {"/pause", "/resume", "/cancel"}:
            _control(runtime_root, command[1:], "", write)
            continue
        elif command == "/guide":
            if not content:
                write("Usage: /guide <instruction>")
            else:
                _control(runtime_root, "guidance", content, write)
            continue
        elif command in {"/console", "/candidate"}:
            _open(runtime_root, command[1:], write)
            continue
        try:
            result = submit_from_omarchy(
                value,
                canonical,
                goal_mode=goal_mode,
                authority_profile=authority_profile,
                runtime_root=runtime_root,
                source=source,
            )
        except (OSError, RuntimeError, ValueError) as error:
            write(f"FAM could not accept the request: {error}")
            continue
        if goal_mode:
            write(
                "Goal accepted · "
                + str(result.get("title") or result.get("goal_id") or "running")
                + ". Use /watch or open the Console; this terminal may be closed."
            )
        else:
            write(_response_text(result))


def _show_status(
    runtime_root: Path, write, *, quiet: bool = False
) -> dict[str, object]:
    try:
        document = widget_request(runtime_root, "/api/v1/status")
    except (OSError, RuntimeError, ValueError) as error:
        if not quiet:
            write(f"Status unavailable: {error}")
        return {}
    goal = document.get("goal")
    if not isinstance(goal, dict):
        if not quiet:
            write("No active or recent goal.")
        return document
    if not quiet:
        write(_goal_line(goal))
    return document


def _watch(runtime_root: Path, write) -> None:
    import time

    write("Following Goal Mode. Press Ctrl+C to return to the prompt.")
    previous = ""
    try:
        while True:
            document = widget_request(runtime_root, "/api/v1/status")
            goal = document.get("goal")
            if not isinstance(goal, dict):
                write("No goal is available.")
                return
            line = _goal_line(goal)
            if line != previous:
                write(line)
                previous = line
            if goal.get("status") in _TERMINAL:
                return
            time.sleep(2)
    except KeyboardInterrupt:
        write("")


def _goal_line(goal: dict[str, object]) -> str:
    status = str(goal.get("status") or "idle").replace("_", " ")
    phase = str(goal.get("phase") or "—")
    plan = goal.get("plan") if isinstance(goal.get("plan"), dict) else {}
    checks = goal.get("checks") if isinstance(goal.get("checks"), dict) else {}
    activity = goal.get("tool") or goal.get("latestAction") or "waiting"
    recovery = ""
    if status == "retry wait":
        recovery = f" · recovery {goal.get('recoveryAttempt', 0)}"
    return (
        f"{status.upper()} · {phase} · step {plan.get('current', 0)}/{plan.get('total', 0)}"
        f" · checks {checks.get('passed', 0)}/{checks.get('total', 0)}"
        f" · {activity}{recovery}"
    )


def _control(runtime_root: Path, operation: str, content: str, write) -> None:
    status = _show_status(runtime_root, lambda *_args: None, quiet=True)
    goal = status.get("goal") if isinstance(status, dict) else None
    if not isinstance(goal, dict) or not goal.get("goalId"):
        write("No active goal is available.")
        return
    payload: dict[str, object] = {"commandId": _command_id()}
    if operation == "guidance":
        payload["content"] = content
    try:
        widget_request(
            runtime_root,
            f"/api/v1/goals/{goal['goalId']}/{operation}",
            document=payload,
        )
        write(f"{operation.replace('_', ' ').title()} accepted.")
    except (OSError, RuntimeError, ValueError) as error:
        write(f"FAM action failed: {error}")


def _open(runtime_root: Path, target: str, write) -> None:
    status = _show_status(runtime_root, lambda *_args: None, quiet=True)
    goal = status.get("goal") if isinstance(status, dict) else None
    path = "/api/v1/console/open"
    payload: dict[str, object] = {"commandId": _command_id()}
    if target == "candidate":
        if not isinstance(goal, dict) or not goal.get("goalId"):
            write("No candidate workspace is available.")
            return
        path = "/api/v1/candidate/open"
        payload["goalId"] = goal["goalId"]
    try:
        widget_request(runtime_root, path, document=payload)
        write(f"Opened {target}.")
    except (OSError, RuntimeError, ValueError) as error:
        write(f"Could not open {target}: {error}")


def _command_id() -> str:
    return "tui-" + uuid4().hex


def _response_text(result: dict[str, object]) -> str:
    task = result.get("engineering_task")
    if isinstance(task, dict):
        for key in ("answer", "content", "summary", "message"):
            if isinstance(task.get(key), str) and task[key].strip():
                return task[key].strip()
    for key in ("answer", "content", "summary", "message"):
        if isinstance(result.get(key), str) and result[key].strip():
            return result[key].strip()
    return json.dumps(result, indent=2, sort_keys=True, default=str)
