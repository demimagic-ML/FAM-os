"""Authenticated Console client used by installed release qualification."""

from __future__ import annotations

import http.cookiejar
import json
import time
import urllib.error
import urllib.request


class ConsoleClient:
    def __init__(self, base_url: str, bootstrap_token: str) -> None:
        self.base_url = base_url.rstrip("/")
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
        )
        document = self._request(
            "POST", "/api/v1/session", {},
            {
                "Authorization": f"Bearer {bootstrap_token}",
                "Origin": self.base_url,
            },
            mutation=False,
        )
        self._csrf = document["csrf_token"]

    def contexts(self) -> list[dict]:
        return self._request("GET", "/api/v1/contexts")["contexts"]

    def snapshot(self) -> dict:
        return self._request("GET", "/api/v1/snapshot")

    def wait_for_context(self, capability_id: str, timeout: float = 30) -> dict:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            context = next((
                item for item in self.contexts()
                if capability_id in item["capability_ids"]
            ), None)
            if context is not None:
                return context
            time.sleep(0.1)
        raise TimeoutError(f"Console context for {capability_id} did not appear")

    def create(
        self, request_id: str, prompt: str, contexts: list[dict],
        capabilities: list[str], verification_required: bool,
    ) -> dict:
        return self._request("POST", "/api/v1/tasks", {
            "request_id": request_id,
            "prompt": prompt,
            "contexts": contexts,
            "required_capabilities": capabilities,
            "verification_required": verification_required,
        })

    def create_verified(
        self, request_id: str, prompt: str, verification: dict,
    ) -> dict:
        return self._request("POST", "/api/v1/tasks", {
            "request_id": request_id,
            "prompt": prompt,
            "verification_required": True,
            "verification": verification,
        })

    def wait_for_approval(self, task_id: str, timeout: float = 180) -> dict:
        return self._wait(
            task_id, lambda item: item.get("approval") is not None, timeout,
            "approval",
        )

    def approve(self, task: dict) -> dict:
        approval = task["approval"]
        return self._request(
            "POST", f"/api/v1/tasks/{task['session_id']}/decision", {
                "expected_revision": task["revision"],
                "approval_id": approval["approval_id"],
                "decision": "approve",
            },
        )

    def wait_for_terminal(self, task_id: str, timeout: float = 180) -> dict:
        return self._wait(
            task_id, lambda item: item.get("result") is not None, timeout,
            "terminal result",
        )

    def task(self, task_id: str) -> dict:
        return self._request("GET", f"/api/v1/tasks/{task_id}")

    def reversal(self, task_id: str) -> dict:
        return self._request("GET", f"/api/v1/tasks/{task_id}/reversal")

    def verifications(self, task_id: str) -> list[dict]:
        return self._request(
            "GET", f"/api/v1/tasks/{task_id}/verification",
        )["runs"]

    def remote_execution(self, task_id: str) -> dict:
        return self._request(
            "GET", f"/api/v1/tasks/{task_id}/remote-execution",
        )

    def remote_recovery(self, task_id: str) -> dict:
        return self._request(
            "GET", f"/api/v1/tasks/{task_id}/remote-recovery",
        )

    def attempt_budget(self, task_id: str) -> dict:
        return self._request(
            "GET", f"/api/v1/tasks/{task_id}/budget",
        )

    def undo(self, task_id: str, request_id: str, expected_revision: int) -> dict:
        return self._request("POST", f"/api/v1/tasks/{task_id}/undo", {
            "request_id": request_id,
            "expected_revision": expected_revision,
        })

    def _wait(self, task_id, predicate, timeout, state_name) -> dict:
        deadline = time.monotonic() + timeout
        latest = None
        while time.monotonic() < deadline:
            latest = self._request("GET", f"/api/v1/tasks/{task_id}")
            if predicate(latest):
                return latest
            if latest.get("state") == "terminal":
                raise RuntimeError(f"task became terminal before {state_name}: {latest}")
            time.sleep(0.1)
        raise TimeoutError(f"task did not reach {state_name}: {latest}")

    def _request(
        self, method: str, path: str, document=None, headers=None,
        *, mutation: bool | None = None,
    ):
        request_headers = dict(headers or {})
        body = None
        if document is not None:
            body = json.dumps(document, separators=(",", ":")).encode()
            request_headers["Content-Type"] = "application/json"
        if mutation is None:
            mutation = method != "GET"
        if mutation:
            request_headers["Origin"] = self.base_url
            csrf = getattr(self, "_csrf", None)
            if csrf is not None:
                request_headers["X-CSRF-Token"] = csrf
        request = urllib.request.Request(
            self.base_url + path, data=body, method=method,
            headers=request_headers,
        )
        try:
            payload = self._opener.open(request, timeout=20).read()
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Console {method} {path} failed: {error.code} {detail}") from error
        return json.loads(payload)
