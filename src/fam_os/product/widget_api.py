"""Stable, compact Goal Mode projection for desktop-shell integrations."""

from __future__ import annotations

import shutil
import subprocess
import json
import os
import re
import threading
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path

from fam_os.adapters.omarchy.commands import uwsm_application_command
from fam_os.core.agent import AgentAuthorityProfile
from fam_os.adapters.linux.command import SubprocessCommandRunner
from fam_os.adapters.linux.nvidia import query_nvidia_resources


_ACTIVE = {"draft", "queued", "running", "retry_wait", "pause_requested", "paused", "cancel_requested", "waiting_approval"}
_COMMAND_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{7,127}\Z")
API_VERSION = 1
PLUGIN_MIN_VERSION = "0.1.0"
SERVICE_VERSION = "0.1.0"


class WidgetStatusApi:
    contract_version = "fam.widget/v1"

    def __init__(
        self, goal_service, *, console_port: int, runtime_root: Path,
        natural_engineering_api=None, residency=None,
        engineering_provider: str | None = None, popen=subprocess.Popen,
        state_root: Path | None = None, command_cache_size: int = 256,
    ) -> None:
        self.goal_service = goal_service
        self.console_port = console_port
        self.runtime_root = runtime_root
        self.natural_engineering_api = natural_engineering_api
        self.residency = residency
        self.engineering_provider = engineering_provider
        self._popen = popen
        self.audit_path = (state_root or runtime_root) / "widget/command-audit.jsonl"
        self._command_cache_size = max(16, command_cache_size)
        self._commands: OrderedDict[str, dict[str, object]] = OrderedDict()
        self._command_lock = threading.Lock()

    def status(self) -> dict[str, object]:
        goal = self.active_goal(include_latest=True)
        return {
            "contractVersion": self.contract_version,
            "apiVersion": API_VERSION,
            "pluginMinVersion": PLUGIN_MIN_VERSION,
            "serviceVersion": SERVICE_VERSION,
            "service": "healthy",
            "observedAt": datetime.now(timezone.utc).isoformat(),
            "consoleUrl": f"http://127.0.0.1:{self.console_port}/",
            "goal": (
                None if goal is None
                else _project_goal(goal, self.engineering_provider)
            ),
            "resources": _resources(self.residency),
        }

    def execute_command(
        self, command_id: str, action: str, callback,
        *, goal_id: str | None = None,
    ) -> dict[str, object]:
        if not isinstance(command_id, str) or not _COMMAND_ID.fullmatch(command_id):
            raise ValueError("commandId must be 8-128 safe identifier characters")
        with self._command_lock:
            cached = self._commands.get(command_id)
            if cached is not None:
                self._commands.move_to_end(command_id)
                return dict(cached)
            result = callback()
            if not isinstance(result, dict):
                raise RuntimeError("widget command result must be an object")
            receipt = {
                **result,
                "commandId": command_id,
                "accepted": True,
            }
            self._append_audit(command_id, action, goal_id, "accepted")
            self._commands[command_id] = dict(receipt)
            while len(self._commands) > self._command_cache_size:
                self._commands.popitem(last=False)
            return receipt

    def _append_audit(
        self, command_id: str, action: str, goal_id: str | None, outcome: str,
    ) -> None:
        self.audit_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.audit_path.parent, 0o700)
        if self.audit_path.is_symlink():
            raise PermissionError("widget audit path cannot be a symbolic link")
        flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(self.audit_path, flags, 0o600)
        try:
            details = os.fstat(descriptor)
            if details.st_uid != os.geteuid():
                raise PermissionError("widget audit log must be owned by the current user")
            document = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "commandId": command_id,
                "action": action,
                "goalId": goal_id,
                "outcome": outcome,
            }
            payload = (json.dumps(document, separators=(",", ":"), sort_keys=True) + "\n").encode()
            os.write(descriptor, payload)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def active_goal(self, *, include_latest: bool = False) -> dict[str, object] | None:
        listing = self.goal_service.list(self.goal_service.owner_id)
        goals = listing.get("goals", [])
        selected = next((item for item in goals if item.get("status") in _ACTIVE), None)
        if selected is None and include_latest and goals:
            selected = goals[0]
        if selected is None:
            return None
        return self.goal_service.inspect(self.goal_service.owner_id, selected["goal_id"])

    def control(self, goal_id: str, action: str, content: str = "") -> dict[str, object]:
        return self.goal_service.control(
            self.goal_service.owner_id, goal_id, action, content,
        )

    def projected_goal(self, goal_id: str) -> dict[str, object]:
        return _project_goal(
            self.goal_service.inspect(self.goal_service.owner_id, goal_id),
            self.engineering_provider,
        )

    def submit(
        self, prompt: str, workspace_root: str, authority_profile: str,
        *, goal_mode: bool,
    ) -> dict[str, object]:
        prompt = _required_text(prompt, "prompt")
        workspace = Path(_required_text(workspace_root, "workspace_root")).resolve(strict=True)
        if not workspace.is_dir():
            raise NotADirectoryError("workspace_root must be a directory")
        profile = AgentAuthorityProfile(authority_profile)
        session_id = "omarchy-agent-launcher"
        if goal_mode:
            draft = self.goal_service.prepare(
                self.goal_service.owner_id, prompt, str(workspace), profile,
                session_id,
            )
            return self.goal_service.activate(
                self.goal_service.owner_id, draft["goal_id"], confirmed=True,
            )
        if self.natural_engineering_api is None:
            raise RuntimeError("natural engineering is unavailable")
        proposal = self.natural_engineering_api.propose(
            self.natural_engineering_api.owner_id, prompt, str(workspace),
            transport_session_id=session_id, authority_profile=profile,
        )
        return self.natural_engineering_api.activate(
            self.natural_engineering_api.owner_id, proposal["proposal_id"],
            session_id, confirmed=True,
        )

    def open_console(self) -> dict[str, object]:
        command = _desktop_open_command(f"http://127.0.0.1:{self.console_port}/")
        process = self._popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        return {"opened": True, "processId": process.pid, "target": "console"}

    def open_candidate(self, goal_id: str) -> dict[str, object]:
        goal = self.goal_service.inspect(self.goal_service.owner_id, goal_id)
        candidate = goal.get("candidate") or {}
        path = (
            candidate.get("candidate_workspace")
            or candidate.get("path")
            or candidate.get("workspace_root")
        )
        if not isinstance(path, str) or not Path(path).is_dir():
            raise FileNotFoundError("candidate workspace is unavailable")
        command = _desktop_open_command(path)
        process = self._popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        return {"opened": True, "processId": process.pid, "target": path}


def _project_goal(
    goal: dict[str, object], engineering_provider: str | None = None,
) -> dict[str, object]:
    live = goal.get("live") or {}
    recovery = goal.get("recovery") or {}
    candidate = goal.get("candidate") or {}
    application = live.get("application_test") or {}
    criteria = goal.get("acceptance_criteria") or []
    engineering_task = goal.get("engineering_task") or {}
    verified = engineering_task.get("verification") or {}
    passed = verified.get("passed")
    if not isinstance(passed, int):
        passed = application.get("assertions_passed", 0)
    created = _timestamp(goal.get("created_at"))
    finished = _timestamp(goal.get("updated_at")) if goal.get("status") in {"completed", "failed", "cancelled"} else datetime.now(timezone.utc).timestamp()
    elapsed = max(0, int(finished - created)) if created else 0
    events = live.get("events") or []
    latest = events[-1] if events else {}
    return {
        "goalId": goal.get("goal_id"),
        "status": goal.get("status"),
        "title": goal.get("title"),
        "phase": live.get("phase") or recovery.get("stage") or goal.get("status"),
        "elapsedSeconds": elapsed,
        "model": live.get("model_ref"),
        "provider": engineering_provider or (
            "codex" if str(live.get("model_ref", "")).startswith("gpt-")
            else "local"
        ),
        "tool": latest.get("tool_id") or latest.get("operation"),
        "latestAction": latest.get("summary") or latest.get("event_kind"),
        "lastActivityAt": live.get("last_activity") or goal.get("updated_at"),
        "recoveryAttempt": recovery.get("attempt", 0),
        "nextRetryAt": recovery.get("next_retry_at"),
        "candidateChanges": _candidate_change_count(candidate),
        "checks": {"passed": passed or 0, "total": len(criteria)},
        "plan": {"current": live.get("step", 0), "total": len(goal.get("plan") or [])},
        "applicationTest": application or None,
    }


def _timestamp(value: object) -> float:
    if not isinstance(value, str):
        return 0
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0


def _required_text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty text")
    return value.strip()


def _candidate_change_count(candidate: dict[str, object]) -> int:
    direct = candidate.get("change_count")
    if isinstance(direct, int) and not isinstance(direct, bool):
        return max(0, direct)
    counts = candidate.get("counts")
    if isinstance(counts, dict):
        return sum(
            max(0, value) for key in ("created", "modified", "deleted")
            if isinstance((value := counts.get(key)), int)
            and not isinstance(value, bool)
        )
    entries = candidate.get("entries")
    if isinstance(entries, list):
        return sum(
            1 for item in entries
            if isinstance(item, dict)
            and item.get("status") in {"created", "modified", "deleted"}
        )
    changes = candidate.get("changes")
    return len(changes) if isinstance(changes, list) else 0


def _resources(residency=None) -> dict[str, object]:
    total = available = 0
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            key, _, value = line.partition(":")
            if key == "MemTotal":
                total = int(value.split()[0]) * 1024
            elif key == "MemAvailable":
                available = int(value.split()[0]) * 1024
    except (OSError, ValueError, IndexError):
        pass
    vram_total = vram_used = 0
    try:
        readings = query_nvidia_resources(SubprocessCommandRunner())
        vram_total = sum(item.memory_total_bytes for item in readings)
        vram_used = sum(item.memory_used_bytes for item in readings)
    except (OSError, RuntimeError, ValueError):
        pass
    models = []
    if residency is not None:
        try:
            models = [
                {
                    "model": item.model_ref,
                    "residentBytes": item.resident_bytes,
                    "acceleratorBytes": item.accelerator_bytes,
                }
                for item in residency.loaded_models()
            ]
        except (OSError, RuntimeError, ValueError):
            pass
    return {
        "ramBytesUsed": max(0, total - available),
        "ramBytesTotal": total,
        "vramBytesUsed": vram_used or None,
        "vramBytesTotal": vram_total or None,
        "residentModels": models,
    }


def _desktop_open_command(target: str) -> tuple[str, ...]:
    opener = shutil.which("xdg-open")
    if opener is None:
        raise FileNotFoundError("xdg-open is unavailable")
    try:
        return uwsm_application_command((opener, target))
    except FileNotFoundError:
        return (opener, target)
