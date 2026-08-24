"""Bounded health observation for process integration services."""

import hashlib
import socket
from urllib.request import build_opener, ProxyHandler

from fam_os.core.engineering import IntegrationHealthKind


class ProcessHealthMonitor:
    def __init__(self, client, sleeper):
        self._client, self._sleep = client, sleeper

    def wait(self, service, receipt, control, require_live):
        check = service.health_check
        for attempt in range(check.maximum_attempts):
            require_live(control)
            if self._healthy(check, receipt):
                raw = f"{receipt.runtime_id}:{attempt}".encode()
                return "health:" + hashlib.sha256(raw).hexdigest()
            if attempt + 1 < check.maximum_attempts:
                self._sleep(check.interval_seconds)
        status = self._client.run(
            self._client.systemctl,
            ("--user", "status", receipt.runtime_id + ".scope", "--no-pager"),
        )
        diagnostic = status.output.strip().replace("\n", " ")[-2_048:]
        raise RuntimeError("process service health check failed: " + diagnostic)

    def _healthy(self, check, receipt):
        if check.kind is IntegrationHealthKind.SIGNED_RECIPE:
            result = self._client.run(
                self._client.systemctl,
                ("--user", "is-active", "--quiet", receipt.runtime_id + ".scope"),
            )
            return result.exit_code == 0
        port = next(
            item.host_port for item in receipt.allocated_ports
            if item.name == check.port_name
        )
        if check.kind is IntegrationHealthKind.TCP:
            try:
                with socket.create_connection(("127.0.0.1", port), check.timeout_seconds):
                    return True
            except OSError:
                return False
        try:
            with build_opener(ProxyHandler({})).open(
                f"http://127.0.0.1:{port}{check.path}", timeout=check.timeout_seconds,
            ) as response:
                return 200 <= response.status < 400
        except OSError:
            return False
