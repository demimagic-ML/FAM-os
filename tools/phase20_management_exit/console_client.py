"""Authenticated Console client for persistent memory controls."""

from tools.phase20_index_exit.scenario import IndexConsoleClient


class MemoryConsoleClient(IndexConsoleClient):
    def documents(self) -> list[dict]:
        return self._request("GET", "/api/v1/memory/documents")["documents"]

    def inspect(self, document_id: str) -> dict:
        return self._request("GET", f"/api/v1/memory/documents/{document_id}")

    def export(self, document_id: str) -> dict:
        return self._request(
            "GET", f"/api/v1/memory/documents/{document_id}/export",
        )

    def receipts(self) -> list[dict]:
        return self._request("GET", "/api/v1/memory/receipts")["receipts"]

    def correct(
        self, document_id: str, request_id: str, expected_digest: str,
        content: str, content_digest: str, confirmed: bool,
    ) -> dict:
        return self._request(
            "POST", f"/api/v1/memory/documents/{document_id}/correct", {
                "request_id": request_id,
                "expected_content_sha256": expected_digest,
                "replacement_content": content,
                "replacement_content_sha256": content_digest,
                "confirmed": confirmed,
            },
        )

    def delete(
        self, document_id: str, request_id: str,
        expected_digest: str, confirmed: bool,
    ) -> dict:
        return self._request(
            "POST", f"/api/v1/memory/documents/{document_id}/delete", {
                "request_id": request_id,
                "expected_content_sha256": expected_digest,
                "confirmed": confirmed,
            },
        )

    def expire(self, grant_id: str, request_id: str, confirmed: bool) -> dict:
        return self._request(
            "POST", f"/api/v1/memory/grants/{grant_id}/expire", {
                "request_id": request_id, "confirmed": confirmed,
            },
        )
