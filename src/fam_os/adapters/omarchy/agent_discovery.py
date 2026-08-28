"""Capability-based discovery of Omarchy-managed agent and model runtimes."""

from __future__ import annotations

import shutil
import socket
import subprocess
from dataclasses import dataclass
from typing import Callable, Iterable
from urllib.parse import urlsplit
from urllib.request import urlopen
import json


@dataclass(frozen=True, slots=True)
class AgentCapability:
    agent_id: str
    executable: str | None
    available: bool
    kind: str
    authentication: str
    selected: bool = False


@dataclass(frozen=True, slots=True)
class InferenceEndpoint:
    endpoint_id: str
    url: str
    reachable: bool
    kind: str
    models: tuple[str, ...] = ()


_AGENTS = {
    "codex": "hosted-engineering",
    "claude": "hosted-engineering",
    "opencode": "agent-harness",
    "copilot": "hosted-engineering",
    "ori": "agent-harness",
}


def discover_agents(
    which: Callable[[str], str | None] = shutil.which,
    default_agent: str | None = None,
    authentication_probe: Callable[[str, str], str] | None = None,
) -> tuple[AgentCapability, ...]:
    probe = authentication_probe or _agent_authentication
    capabilities = []
    for name, kind in _AGENTS.items():
        executable = which(name)
        capabilities.append(AgentCapability(
            name, executable, executable is not None, kind,
            probe(name, executable) if executable else "unavailable",
            name == default_agent,
        ))
    return tuple(capabilities)


def discover_inference_endpoints(
    urls: Iterable[tuple[str, str, str]] = (
        ("ollama", "http://127.0.0.1:11434", "ollama"),
        ("fam-ollama", "http://127.0.0.1:11435", "ollama"),
        ("lm-studio", "http://127.0.0.1:1234", "openai-compatible"),
    ),
    *,
    connect: Callable[..., object] = socket.create_connection,
    fetch_json: Callable[[str], object] | None = None,
) -> tuple[InferenceEndpoint, ...]:
    fetch = fetch_json or _fetch_json
    endpoints = []
    for endpoint_id, url, kind in urls:
        parsed = urlsplit(url)
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        reachable = False
        try:
            connection = connect((parsed.hostname, port), timeout=0.2)
            close = getattr(connection, "close", None)
            if close is not None:
                close()
            reachable = True
        except OSError:
            pass
        models = _endpoint_models(fetch, url, kind) if reachable else ()
        endpoints.append(InferenceEndpoint(endpoint_id, url, reachable, kind, models))
    return tuple(endpoints)


def browser_capabilities(
    which: Callable[[str], str | None] = shutil.which,
) -> tuple[AgentCapability, ...]:
    return tuple(
        AgentCapability(name, path, path is not None, "browser", "not-required")
        for name in ("chromium", "google-chrome-stable", "firefox")
        if (path := which(name)) is not None
    )


def _agent_authentication(agent_id: str, executable: str) -> str:
    if agent_id != "codex":
        return "unknown"
    try:
        result = subprocess.run(
            (executable, "login", "status"), check=False, capture_output=True,
            text=True, timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"
    return "authenticated" if result.returncode == 0 else "unauthenticated"


def _fetch_json(url: str) -> object:
    with urlopen(url, timeout=1) as response:
        return json.load(response)


def _endpoint_models(
    fetch: Callable[[str], object], url: str, kind: str,
) -> tuple[str, ...]:
    endpoint = url.rstrip("/") + ("/api/tags" if kind == "ollama" else "/v1/models")
    try:
        document = fetch(endpoint)
    except (OSError, RuntimeError, ValueError):
        return ()
    if not isinstance(document, dict):
        return ()
    records = document.get("models" if kind == "ollama" else "data")
    if not isinstance(records, list):
        return ()
    key = "name" if kind == "ollama" else "id"
    return tuple(
        value for item in records
        if isinstance(item, dict)
        and isinstance((value := item.get(key)), str)
        and value.strip()
    )
