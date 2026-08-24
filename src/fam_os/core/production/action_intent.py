"""Deterministic ingress firewall for action-shaped natural language."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path

from fam_os.applications import WORKSPACE_PATCH_CAPABILITY
from fam_os.core.engineering import EngineeringAuthority


CREATE_DIRECTORY_CAPABILITY = "os.directory.create"

_MACHINE_NOUNS = (
    r"file|folder|directory|document|workspace|project|application|app|program|"
    r"process|service|window|tab|device|disk|drive|volume|package|account|"
    r"message|email|calendar|event|record|setting|permission|network|connection"
)


@dataclass(frozen=True, slots=True)
class ActionIntentDecision:
    action_shaped: bool
    capability_id: str | None = None
    target_path: Path | None = None
    needs_input: bool = False
    safe_message: str = ""
    required_engineering_authorities: tuple[EngineeringAuthority, ...] = ()


@dataclass(frozen=True, slots=True)
class PendingAction:
    directory_name: str | None
    expires_at: float


class ActionIntentFirewall:
    """Recognize authority-bearing requests before any model is selected."""

    def __init__(self, ttl_seconds: float = 900.0, maximum_pending: int = 128) -> None:
        if ttl_seconds <= 0 or maximum_pending <= 0:
            raise ValueError("pending action bounds must be positive")
        self._ttl = ttl_seconds
        self._maximum = maximum_pending
        self._pending: dict[str, PendingAction] = {}

    def inspect(
        self, prompt: str, session_id: str, workspace_path: Path | None = None,
    ) -> ActionIntentDecision:
        now = time.monotonic()
        self._expire(now)
        pending = self._pending.get(session_id)
        if pending is not None:
            continued = _continued_target(prompt, pending.directory_name)
            if continued is not None:
                self._pending.pop(session_id, None)
                return _create_decision(continued)
            if _cancelled(prompt):
                self._pending.pop(session_id, None)
                return ActionIntentDecision(False)
        if workspace_path is not None and _workspace_implementation_request(prompt):
            return ActionIntentDecision(
                True, WORKSPACE_PATCH_CAPABILITY,
                safe_message=(
                    "A bounded workspace patch can be proposed from observed files. "
                    "No file will change before preview and owner approval."
                ),
                required_engineering_authorities=(
                    EngineeringAuthority.OBSERVE,
                    EngineeringAuthority.PROPOSE,
                    EngineeringAuthority.MODIFY,
                ),
            )
        if not _direct_action(prompt):
            return ActionIntentDecision(False)
        if not _create_directory_request(prompt):
            authorities = recognize_engineering_authorities(prompt)
            return ActionIntentDecision(
                True,
                safe_message=(
                    "This request describes a machine action, but no matching "
                    "authorized capability is available. No action was attempted."
                ),
                required_engineering_authorities=authorities,
            )
        target = _absolute_path(prompt)
        name = _directory_name(prompt)
        if target is not None:
            if name is not None and target.name != name:
                target = target / name
            return _create_decision(target)
        if workspace_path is not None and name is not None:
            return _create_decision(workspace_path / name)
        self._remember(session_id, PendingAction(name, now + self._ttl))
        detail = "absolute target path" if name is None else "absolute parent directory"
        return ActionIntentDecision(
            True, CREATE_DIRECTORY_CAPABILITY, needs_input=True,
            safe_message=(
                f"A create-directory action needs an exact {detail}. "
                "Provide that path in your next message; no action has been attempted."
            ),
        )

    def _remember(self, session_id: str, pending: PendingAction) -> None:
        if len(self._pending) >= self._maximum and session_id not in self._pending:
            oldest = next(iter(self._pending))
            self._pending.pop(oldest, None)
        self._pending[session_id] = pending

    def _expire(self, now: float) -> None:
        for session_id, pending in tuple(self._pending.items()):
            if pending.expires_at <= now:
                self._pending.pop(session_id, None)


def _create_decision(path: Path) -> ActionIntentDecision:
    return ActionIntentDecision(
        True, CREATE_DIRECTORY_CAPABILITY, path,
        safe_message="A scoped create-directory capability was resolved.",
        required_engineering_authorities=(
            EngineeringAuthority.PROPOSE,
            EngineeringAuthority.MODIFY,
        ),
    )


def recognize_engineering_authorities(
    prompt: str,
) -> tuple[EngineeringAuthority, ...]:
    """Classify required authority names without admitting or granting them."""

    normalized = " ".join(prompt.casefold().split())
    matches: set[EngineeringAuthority] = set()
    for authority, patterns in _AUTHORITY_PATTERNS:
        if any(re.search(pattern, normalized) is not None for pattern in patterns):
            matches.add(authority)
    if matches and EngineeringAuthority.PROPOSE not in matches:
        matches.add(EngineeringAuthority.PROPOSE)
    return tuple(authority for authority in EngineeringAuthority if authority in matches)


_AUTHORITY_PATTERNS = (
    (EngineeringAuthority.OBSERVE, (
        r"\b(?:inspect|observe|read|list|show|scan|search|find|diagnose|"
        r"analy[sz]e|review|understand|trace)\b",
    )),
    (EngineeringAuthority.PROPOSE, (r"\b(?:plan|propose|draft|preview)\b",)),
    (EngineeringAuthority.MODIFY, (
        r"\b(?:create|make|add|write|edit|modify|implement|fix|repair|refactor|"
        r"migrate|redesign|generate|delete|remove|move|rename|copy|save|"
        r"install|uninstall|update|set|toggle|format|deploy|push|publish)\b",
    )),
    (EngineeringAuthority.EXECUTE, (
        r"\b(?:run|execute|launch|start|stop|restart|shutdown|install|uninstall|"
        r"deploy|command|build|test|tests|lint|type[- ]?check|compile|profile|"
        r"debug)\b",
    )),
    (EngineeringAuthority.NETWORK, (
        r"\b(?:network|connect|disconnect|download|upload|fetch|curl|remote|registry|internet|push|publish|deploy)\b",
    )),
    (EngineeringAuthority.PUBLISH, (
        r"\b(?:publish|upload|push|send|post|deploy|pull request|merge request)\b",
    )),
    (EngineeringAuthority.RAW_SHELL, (
        r"\b(?:raw shell|shell command|bash|zsh|powershell|terminal command)\b",
    )),
    (EngineeringAuthority.HOST_ADMIN, (
        r"\b(?:sudo|root access|administrator|admin access|systemd|mount|unmount|format disk|host-wide)\b",
    )),
    (EngineeringAuthority.SECRET_USE, (
        r"\b(?:secret|credential|password|access token|api key|private key)\b",
    )),
    (EngineeringAuthority.GLOBAL_INSTALL, (
        r"\b(?:global install|install globally|system-wide install|apt install|dnf install|pacman -s)\b",
    )),
    (EngineeringAuthority.PRODUCTION_MUTATE, (
        r"\b(?:production|prod environment|live environment|deploy to prod)\b",
    )),
    (EngineeringAuthority.POLICY_CHANGE, (
        r"\b(?:change policy|security policy|permission policy|firewall rule|verification policy)\b",
    )),
    (EngineeringAuthority.PROTECTED_REF_WRITE, (
        r"\b(?:force[- ]push|protected (?:branch|ref)|push to main|push to master)\b",
    )),
    (EngineeringAuthority.SELF_UPDATE, (
        r"\b(?:update fam_os|update fam os|fam_os self-update|self-update fam)\b",
    )),
)


def _direct_action(prompt: str) -> bool:
    normalized = " ".join(prompt.casefold().split())
    match = re.match(
        r"^(?:(?:hey\s+)?fam[,\s]+|(?:please|kindly|now)\s+|"
        r"(?:can|could|would|will)\s+you\s+(?:please\s+)?|"
        r"i(?:'d|\s+would)\s+like\s+you\s+to\s+|"
        r"i\s+(?:want|need)\s+you\s+to\s+|go\s+ahead\s+and\s+)?"
        r"(create|make|add|delete|remove|move|rename|copy|open|launch|"
        r"implement|install|uninstall|save|write|edit|modify|run|execute|send|post|"
        r"download|upload|publish|push|deploy|use|close|shutdown|restart|start|stop|"
        r"connect|disconnect|mount|unmount|format|turn|set|toggle|lock|unlock|print|"
        r"self-update)\b(.*)$",
        normalized,
    )
    if match is None:
        return False
    verb, remainder = match.groups()
    if verb == "implement":
        code_only = re.search(
            r"\b(?:python|javascript|typescript|rust|go|java|kotlin|c\+\+|"
            r"function|class|algorithm|code block)\b",
            remainder,
        ) is not None
        machine_target = re.search(
            r"\b(?:file|path|workspace|repository|project|application|service|"
            r"package|system|host|remote)\b|/",
            remainder,
        ) is not None
        if code_only and not machine_target:
            return False
    if verb == "write":
        return re.search(
            rf"\b(?:{_MACHINE_NOUNS}|path)\b|/",
            remainder,
        ) is not None
    if verb == "use":
        # "Use this interface/bridge" is commonly a conversational request,
        # not evidence of a machine effect.  Require the same concrete machine
        # target that the other ambiguous verbs require before withholding it
        # behind application authority.
        return re.search(
            rf"\b(?:{_MACHINE_NOUNS}|path)\b|/",
            remainder,
        ) is not None
    if verb in {"create", "make", "add"}:
        return re.search(
            rf"\b(?:{_MACHINE_NOUNS})\b|/",
            remainder,
        ) is not None
    if verb in {"start", "stop", "turn", "set", "toggle"}:
        return re.search(
            rf"\b(?:{_MACHINE_NOUNS}|on|off)\b|/", remainder,
        ) is not None
    return True


def _create_directory_request(prompt: str) -> bool:
    normalized = " ".join(prompt.casefold().split())
    return (
        re.search(r"\b(?:create|make|add)\b", normalized) is not None
        and re.search(r"\b(?:folder|directory)\b", normalized) is not None
    )


def _workspace_implementation_request(prompt: str) -> bool:
    normalized = " ".join(prompt.casefold().split())
    if re.match(r"^(?:explain|describe|show me how|how (?:can|do|would))\b", normalized):
        return False
    return re.search(
        r"\b(?:implement(?:\s+it|\s+the\s+(?:plan|change|fix))?|"
        r"apply\s+the\s+(?:plan|changes?|fix)|"
        r"make\s+the\s+(?:planned\s+)?changes?)\b",
        normalized,
    ) is not None


def _directory_name(prompt: str) -> str | None:
    match = re.search(
        r"\b(?:name\s+it|named?|called)\s+[\"']?"
        r"([a-zA-Z0-9][a-zA-Z0-9._ -]{0,127})",
        prompt,
        flags=re.IGNORECASE,
    )
    if match is None:
        match = re.search(
            r"\b(?:folder|directory)\s+(?:named?\s+|called\s+)?"
            r"(?!(?:at|in|under)\b)[\"']?"
            r"([a-zA-Z0-9][a-zA-Z0-9._-]{0,127})",
            prompt,
            flags=re.IGNORECASE,
        )
    if match is None:
        return None
    value = re.split(
        r"\s*(?:,|;|\bwith\s+no\b|\bno\s+content\b|\bempty\b)",
        match.group(1), maxsplit=1, flags=re.IGNORECASE,
    )[0].strip(" \"'.")
    if not value or value in {".", ".."} or "/" in value or "\x00" in value:
        return None
    return value


def _continued_target(prompt: str, directory_name: str | None) -> Path | None:
    path = _absolute_path(prompt)
    if path is None:
        return None
    if directory_name is not None and path.name != directory_name:
        return path / directory_name
    return path


def _absolute_path(prompt: str) -> Path | None:
    stripped = prompt.strip()
    quoted = re.search(r"[\"'](/[^\"'\r\n]+)[\"']", stripped)
    unquoted = re.search(r"(?<!\S)(/[^\s,;]+)", stripped)
    value = (quoted or unquoted)
    if value is None:
        return None
    path_text = value.group(1).rstrip(".!?")
    if len(path_text.encode("utf-8")) > 4096 or "\x00" in path_text:
        return None
    path = Path(path_text)
    if not path.is_absolute() or ".." in path.parts or path == Path("/"):
        return None
    return path


def _cancelled(prompt: str) -> bool:
    return " ".join(prompt.casefold().split()) in {
        "cancel", "never mind", "nevermind", "stop", "forget it",
    }
