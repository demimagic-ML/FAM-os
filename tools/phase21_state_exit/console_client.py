"""Authenticated Console client for installed trusted-peer controls."""

from urllib.parse import quote

from tools.phase19_exit.console_client import ConsoleClient


class PeerConsoleClient(ConsoleClient):
    def create_remote(
        self,
        request_id: str,
        prompt: str,
        authority: dict,
        *,
        verification_required: bool = True,
    ) -> dict:
        return self._request("POST", "/api/v1/tasks", {
            "request_id": request_id,
            "prompt": prompt,
            "verification_required": verification_required,
            "remote_authority": authority,
        })

    def peers(self) -> list[dict]:
        return self._request("GET", "/api/v1/peers?offset=0&limit=100")["peers"]

    def receipts(self) -> list[dict]:
        return self._request(
            "GET", "/api/v1/peers/receipts?offset=0&limit=100",
        )["control_receipts"]

    def context_evidence(self) -> list[dict]:
        return self._request(
            "GET", "/api/v1/peers/context-evidence?offset=0&limit=100",
        )["context_evidence"]

    def probe(self, enrollment_id: str, request_id: str) -> dict:
        return self._request(
            "POST", f"/api/v1/peers/{quote(enrollment_id, safe='')}/probe",
            {"request_id": request_id},
        )

    def privacy(
        self, enrollment_id: str, request_id: str, expected_revision: int,
        confirmed: bool, *, raw_content_allowed: bool = False,
        maximum_context_bytes: int = 4096,
    ) -> dict:
        return self._request(
            "POST", f"/api/v1/peers/{quote(enrollment_id, safe='')}/privacy",
            {
                "request_id": request_id, "expected_revision": expected_revision,
                "confirmed": confirmed, "reason_code": "owner.configured",
                "maximum_context_bytes": maximum_context_bytes,
                "sensitivities": ["private"],
                "purpose_ids": ["assist"], "workspace_ids": ["workspace:installed"],
                "raw_content_allowed": raw_content_allowed,
            },
        )

    def context(self, enrollment_id: str, document: dict) -> dict:
        return self._request(
            "POST", f"/api/v1/peers/{quote(enrollment_id, safe='')}/context",
            document,
        )

    def revoke(
        self, enrollment_id: str, request_id: str, expected_revision: int,
        confirmed: bool,
    ) -> dict:
        return self._request(
            "POST", f"/api/v1/peers/{quote(enrollment_id, safe='')}/revoke",
            {
                "request_id": request_id, "expected_revision": expected_revision,
                "confirmed": confirmed, "reason_code": "owner.revoked",
            },
        )
