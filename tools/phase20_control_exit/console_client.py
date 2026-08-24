"""Authenticated Console client for live adaptation evidence and controls."""

from urllib.parse import quote

from tools.phase19_exit.console_client import ConsoleClient


class AdaptationConsoleClient(ConsoleClient):
    def status(self) -> dict:
        return self._request("GET", "/api/v1/adaptation/status")

    def snapshots(self) -> list[dict]:
        return self._collection("snapshots")

    def prewarms(self) -> list[dict]:
        return self._collection("prewarms")

    def health(self) -> list[dict]:
        return self._collection("health")

    def drift(self) -> list[dict]:
        return self._collection("drift_reports", "drift")

    def receipts(self) -> list[dict]:
        return self._collection("control_receipts", "receipts")

    def control(
        self,
        operation: str,
        request_id: str,
        confirmed: bool,
        workflow_id: str | None = None,
    ) -> dict:
        if workflow_id is None:
            path = f"/api/v1/adaptation/{operation}"
        else:
            workflow = quote(workflow_id, safe="")
            path = f"/api/v1/adaptation/workflows/{workflow}/{operation}"
        return self._request(
            "POST",
            path,
            {
                "request_id": request_id,
                "confirmed": confirmed,
            },
        )

    def _collection(self, name: str, path: str | None = None) -> list[dict]:
        document = self._request("GET", f"/api/v1/adaptation/{path or name}")
        return document[name]
