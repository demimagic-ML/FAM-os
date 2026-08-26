"""Injectable JSON-over-HTTP transport for the Ollama adapter."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Protocol

from fam_os.adapters.ollama.errors import OllamaTransportError


JsonObject = dict[str, object]


class JsonTransport(Protocol):
    def request(
        self,
        method: str,
        url: str,
        payload: JsonObject | None,
        timeout_seconds: float,
    ) -> JsonObject: ...


class UrllibJsonTransport:
    def request(
        self,
        method: str,
        url: str,
        payload: JsonObject | None,
        timeout_seconds: float,
    ) -> JsonObject:
        scheme = urllib.parse.urlsplit(url).scheme.lower()
        if scheme not in {"http", "https"}:
            raise OllamaTransportError("Ollama URL must use HTTP or HTTPS")
        body = json.dumps(payload).encode() if payload is not None else None
        request = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                decoded = json.loads(response.read())
        except urllib.error.HTTPError as exc:
            try:
                detail = exc.read(4_097).decode("utf-8", "replace").strip()
            except OSError:
                detail = ""
            if len(detail) > 4_096:
                detail = detail[:4_096].rstrip() + "…"
            message = f"Ollama {method} request returned HTTP {exc.code}"
            if detail:
                try:
                    document = json.loads(detail)
                    detail = str(document.get("error") or detail) if isinstance(document, dict) else detail
                except json.JSONDecodeError:
                    pass
                message += f": {detail}"
            raise OllamaTransportError(message) from exc
        except (urllib.error.URLError, TimeoutError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise OllamaTransportError(f"Ollama {method} request failed") from exc
        if not isinstance(decoded, dict):
            raise OllamaTransportError("Ollama response must be a JSON object")
        return decoded
